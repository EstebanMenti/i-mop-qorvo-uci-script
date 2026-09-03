"""Cliente UCI de alto nivel: comandos del grupo Core, correlacion cmd<->resp.

Ver docs/arquitectura.md Seccion 3.3. Las notificaciones (`MT.NOTIFICATION`)
que llegan mientras se espera una Response no se descartan: se acumulan en
`UciClient.notifications` para que quien las necesite (p. ej. la suite de
validacion, fase F6) pueda inspeccionarlas.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from dwm3001c_uci.core.errors import UciTimeoutError
from dwm3001c_uci.core.models import (
    AppConfigResult,
    DeviceInfo,
    SessionInitResult,
    parse_app_config_response,
    parse_device_info,
    parse_session_init_result,
)
from dwm3001c_uci.transport.serial_link import Transport
from dwm3001c_uci.uci.app_config import encode_app_config
from dwm3001c_uci.uci.enums import (
    AppConfigParam,
    DeviceRole,
    DeviceType,
    Gid,
    MessageType,
    MultiNodeMode,
    OidCore,
    OidRanging,
    OidSession,
    RangingRoundUsage,
    SessionType,
    Status,
)
from dwm3001c_uci.uci.framing import StreamDecoder, UciMessage, encode_packet, split_into_packets

DEFAULT_TIMEOUT_S = 2.0
DEFAULT_READ_CHUNK_SIZE = 256


class UciClient:
    """Envia comandos UCI y correlaciona la Response con el Command que la origino."""

    def __init__(
        self,
        transport: Transport,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        read_chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
    ) -> None:
        self._transport = transport
        self._timeout_s = timeout_s
        self._read_chunk_size = read_chunk_size
        self._decoder = StreamDecoder()
        self.notifications: list[UciMessage] = []

    def _send_command_and_wait_response(self, gid: int, oid: int, payload: bytes) -> UciMessage:
        for packet in split_into_packets(MessageType.COMMAND, gid, oid, payload):
            self._transport.write(encode_packet(packet))

        deadline = time.monotonic() + self._timeout_s
        while time.monotonic() < deadline:
            chunk = self._transport.read(self._read_chunk_size)
            if not chunk:
                continue

            response: UciMessage | None = None
            for message in self._decoder.feed(chunk):
                if message.mt == MessageType.RESPONSE and message.gid == gid and message.oid == oid:
                    # No retornar de inmediato: un mismo lote decodificado puede
                    # traer notificaciones antes o despues de esta Response (se
                    # observo contra hardware real, ver docs/protocolo-uci.md),
                    # y hay que terminar de procesarlo para no perderlas.
                    response = message
                elif message.mt == MessageType.NOTIFICATION:
                    self.notifications.append(message)
                # Una Response de otro GID/OID mientras se espera esta seria
                # un desorden del firmware o de otro comando concurrente: se
                # ignora en vez de fallar, y queda fuera de este cliente
                # simple detectar ese caso (ver docs/plan-implementacion.md).

            if response is not None:
                return response

        raise UciTimeoutError(
            f"timeout de {self._timeout_s}s esperando Response de GID=0x{gid:02X} OID=0x{oid:02X}"
        )

    def poll_notifications(self, duration_s: float = 0.0) -> list[UciMessage]:
        """Lee del transporte y decodifica notificaciones espontaneas, sin esperar ningun comando.

        **Importante:** `UciClient` no tiene ningun hilo de fondo escuchando
        el puerto -- los bytes solo se leen y decodifican como efecto
        colateral de `_send_command_and_wait_response()` (al enviar un
        comando y esperar su Response). Si el código llamador simplemente
        duerme (`time.sleep()`) esperando notificaciones espontáneas (p. ej.
        `RANGING_DATA_NTF` mientras una sesión de ranging está activa, sin
        enviar ningún otro comando), **no va a ver casi ninguna**: los bytes
        se acumulan sin leer en el buffer del sistema operativo hasta la
        próxima llamada que sí lea el transporte, momento en el que sólo se
        alcanza a procesar lo que entra en un puñado de lecturas antes de
        encontrar la Response que esa llamada esperaba (confirmado contra
        hardware real: sólo se observaban 2-3 notificaciones por ronda de
        `ranging_start()`/`ranging_stop()`, nunca las decenas esperadas
        durante una ventana de varios segundos). Para observar notificaciones
        durante una ventana de tiempo, llamar a este método en un loop en vez
        de dormir.

        Devuelve las notificaciones nuevas decodificadas en esta llamada
        (también quedan agregadas a `self.notifications`, igual que las que
        llegan durante `_send_command_and_wait_response()`).
        """
        new_notifications: list[UciMessage] = []
        deadline = time.monotonic() + duration_s
        while True:
            chunk = self._transport.read(self._read_chunk_size)
            if chunk:
                for message in self._decoder.feed(chunk):
                    if message.mt == MessageType.NOTIFICATION:
                        self.notifications.append(message)
                        new_notifications.append(message)
                    # Una Response sin ningun comando en curso esperandola no
                    # deberia pasar en uso normal; este metodo no falla por
                    # eso, simplemente la ignora (no hay a quien devolversela).
            if time.monotonic() >= deadline:
                break
        return new_notifications

    def reset(self) -> Status:
        """Envia `CORE_RESET`. Payload confirmado contra hardware real: 1 byte (0x00)."""
        message = self._send_command_and_wait_response(Gid.CORE, OidCore.RESET, b"\x00")
        return Status(message.payload[0])

    def get_device_info(self) -> DeviceInfo:
        """Envia `CORE_GET_DEVICE_INFO` y devuelve la respuesta decodificada."""
        message = self._send_command_and_wait_response(Gid.CORE, OidCore.GET_DEVICE_INFO, b"")
        return parse_device_info(message.payload)

    def get_caps_raw(self) -> tuple[Status, bytes]:
        """Envia `CORE_GET_CAPS` sin decodificar la lista TLV de capacidades.

        La decodificacion completa de parametros de capacidad queda pendiente
        (no forma parte de esta fase, ver docs/plan-implementacion.md F3).
        """
        message = self._send_command_and_wait_response(Gid.CORE, OidCore.GET_CAPS, b"")
        return Status(message.payload[0]), message.payload[1:]

    def session_init(self, session_id: int, session_type: SessionType) -> SessionInitResult:
        """Envia `SESSION_INIT`. Payload: session_id (4 bytes LE) + session_type (1 byte).

        `session_id` es el identificador que propone el host. **El firmware no
        esta obligado a devolverlo tal cual**: confirmado contra hardware real
        que puede asignar un `session_handle` distinto (ver
        `SessionInitResult.session_handle` y docs/protocolo-uci.md). Todos los
        demas comandos de este grupo (`session_deinit`, `get_session_state`)
        deben usar ese `session_handle`, no el `session_id` original.
        """
        payload = session_id.to_bytes(4, "little") + bytes([session_type])
        message = self._send_command_and_wait_response(Gid.SESSION, OidSession.INIT, payload)
        return parse_session_init_result(message.payload)

    def session_set_app_config(
        self,
        session_handle: int,
        *,
        device_type: DeviceType,
        device_role: DeviceRole,
        device_mac_address: int,
        dst_mac_addresses: Sequence[int],
        multi_node_mode: MultiNodeMode = MultiNodeMode.UNICAST,
        ranging_round_usage: RangingRoundUsage = RangingRoundUsage.DS_TWR_DEFERRED,
        channel_number: int = 9,
        sts_config: int = 0,
        rframe_config: int = 3,
        schedule_mode: int = 1,
        preamble_code_index: int = 10,
        sfd_id: int = 2,
        slot_duration_us: int = 2400,
        ranging_interval_ms: int = 200,
        slots_per_rr: int = 25,
        vendor_id: int = 0x0708,
        static_sts_iv: int = 0x060504030201,
        sts_length: int = 1,
        aoa_result_req: int = 1,
        result_report_config: int = 0x0B,
        uwb_initiation_time: int = 0,
        hopping_mode: int = 0,
        block_stride_length: int = 0,
        rssi_reporting: int = 0,
        max_number_of_measurements: int = 0,
    ) -> AppConfigResult:
        """Envia `SESSION_SET_APP_CONFIG` con un conjunto minimo de parametros.

        No es un codec TVS generico como el de la libreria de referencia de
        Qorvo, que soporta los ~90 parametros de `App.defs`. Cubre solo lo
        necesario para levantar una sesion basica de TWR (Two-Way Ranging):

        - Los 5 que `run_fira_twr.py` del SDK etiqueta como *"Fira
          Mandatory/minimal session config"*: `device_type`, `device_role`,
          `multi_node_mode`, `ranging_round_usage`, `device_mac_address`.
        - `dst_mac_addresses` y `channel_number`, necesarios para que dos
          dispositivos se encuentren en el mismo canal.
        - `sts_config`, `rframe_config`, `schedule_mode`,
          `preamble_code_index`, `sfd_id`, `slot_duration_us`,
          `ranging_interval_ms`, `slots_per_rr`: sin enums propios todavia
          (se pasan como `int` crudo), con los mismos valores por defecto que
          usa `run_fira_twr.py`. **Confirmado contra hardware real** que son
          necesarios ademas de los 5 "mandatory": con solo esos 5, el
          firmware acepta cada parametro pero `RANGING_START` sigue
          devolviendo `Status.ERROR_SESSION_NOT_CONFIGURED`.
        - `vendor_id`/`static_sts_iv`: clave STS estatica. Los valores por
          defecto (`0x0708`/`0x060504030201`) son los mismos "hardcoded" que
          usa `run_fira_twr.py` del SDK **y** los que muestra por defecto el
          firmware CLI de texto (`INITF`/`RESPF` sin opciones, confirmado
          contra `i-mop-qorvo-CLI-script/docs/referencia-comandos-fw110.md`:
          `VENDOR_ID: "07:08"`, `STATIC_STS_IV: "01:02:03:04:05:06"`). Para
          que dos dispositivos completen un ranging real en modo STS estatico
          (`sts_config=0`), **ambos necesitan la misma clave** — dejar el
          default acá facilita interoperar con una placa CLI sin tener que
          pasarlo a mano. Confirmado contra el Developer Manual del SDK
          (Tabla 7.6) que la CLI expone esta misma clave como un solo valor
          de 8 bytes (`VUPPER`, `vUpper64`), del cual `vendor_id`/
          `static_sts_iv` son los dos "pedazos" en los que UCI la separa.
        - `sts_length`: cantidad de simbolos por segmento STS (`0`=32,
          `1`=64, `2`=128). El default (`1`, 64 simbolos) coincide con lo que
          documenta la Tabla 7.7 del Developer Manual para el perfil
          `PRFSET=BPRF4` (el que usa la CLI por defecto en `INITF`/`RESPF`) y
          con el default de `run_fira_twr.py` del SDK. A diferencia de
          `vendor_id`/`static_sts_iv`, **este parametro no se fijaba en
          absoluto** en versiones anteriores de este cliente — el firmware
          UCI usaba su propio default, sin confirmar si coincidia con 64
          simbolos. Si no coincide con el del otro extremo, la secuencia STS
          generada en cada lado no es la misma y el receptor no puede
          decodificar la trama de ranging del otro dispositivo (efecto
          esperado: timeout en cada ronda, sin ningun otro sintoma).
        - `aoa_result_req`, `result_report_config`, `uwb_initiation_time`,
          `hopping_mode`, `block_stride_length`, `rssi_reporting`,
          `max_number_of_measurements`: agregados a partir de comparar este
          metodo contra `run_fira_twr.py` del SDK -- el script de referencia
          *propio de Qorvo* para correr TWR por UCI (no la CLI de texto).
          Ese script los incluye en su lista de `app_configs` para toda
          corrida, junto a los parametros ya cubiertos arriba; este cliente
          no los fijaba en absoluto y dejaba que el firmware aplicara su
          propio default. Valores por defecto identicos a los de
          `run_fira_twr.py` (`aoa_result_req=1` "all-enabled",
          `result_report_config=0x0B` "tof|azimuth|fom", el resto en su
          valor mas conservador/deshabilitado). **`[Sin confirmar]`** que
          alguno de estos sea la causa de un `RANGING_RX_TIMEOUT` persistente
          documentado en `docs/ranging-mixto-cli-uci.md` -- se agregan para
          alcanzar paridad con la implementacion de referencia de Qorvo y
          descartar (o confirmar) esa hipotesis contra hardware real.
        - `NUMBER_OF_CONTROLEES`: agregado como `len(dst_mac_addresses)` (no
          es un parametro nuevo del metodo). Confirmado como necesario --
          no solo recomendado -- contra un proyecto hermano independiente
          (`uwb-qorvo-tools`, Raspberry Pi + UCI local + CLI remoto por BLE,
          con ranging real medido con exito) que lo fija explicitamente en
          cada sesion unicast.

        No soporta el resto de los parametros de `App.defs` (STS
        provisionado/con clave, diagnosticos Qorvo, DL-TDoA, ...).

        Validado contra hardware real con una sola placa (los primeros 18
        parametros, sin los 7 agregados mas arriba para paridad con
        `run_fira_twr.py`): el firmware acepta ese subconjunto sin rechazar
        ningun parametro, y permite completar rondas de ranging (ver
        `ranging_start`). **`[Sin confirmar]`** que el firmware acepte
        tambien los 7 parametros nuevos sin rechazarlos -- pendiente de
        confirmar en la proxima corrida contra hardware real. Ver
        docs/plan-implementacion.md.
        """
        dst_mac_addresses_list = list(dst_mac_addresses)
        params: list[tuple[int, int | Sequence[int]]] = [
            (AppConfigParam.DEVICE_TYPE, int(device_type)),
            (AppConfigParam.DEVICE_ROLE, int(device_role)),
            (AppConfigParam.MULTI_NODE_MODE, int(multi_node_mode)),
            (AppConfigParam.NUMBER_OF_CONTROLEES, len(dst_mac_addresses_list)),
            (AppConfigParam.RANGING_ROUND_USAGE, int(ranging_round_usage)),
            (AppConfigParam.DEVICE_MAC_ADDRESS, device_mac_address),
            (AppConfigParam.DST_MAC_ADDRESS, dst_mac_addresses_list),
            (AppConfigParam.CHANNEL_NUMBER, channel_number),
            (AppConfigParam.STS_CONFIG, sts_config),
            (AppConfigParam.RFRAME_CONFIG, rframe_config),
            (AppConfigParam.SCHEDULE_MODE, schedule_mode),
            (AppConfigParam.PREAMBLE_CODE_INDEX, preamble_code_index),
            (AppConfigParam.SFD_ID, sfd_id),
            (AppConfigParam.SLOT_DURATION, slot_duration_us),
            (AppConfigParam.RANGING_INTERVAL, ranging_interval_ms),
            (AppConfigParam.SLOTS_PER_RR, slots_per_rr),
            (AppConfigParam.VENDOR_ID, vendor_id),
            (AppConfigParam.STATIC_STS_IV, static_sts_iv),
            (AppConfigParam.STS_LENGTH, sts_length),
            (AppConfigParam.AOA_RESULT_REQ, aoa_result_req),
            (AppConfigParam.RESULT_REPORT_CONFIG, result_report_config),
            (AppConfigParam.UWB_INITIATION_TIME, uwb_initiation_time),
            (AppConfigParam.HOPPING_MODE, hopping_mode),
            (AppConfigParam.BLOCK_STRIDE_LENGTH, block_stride_length),
            (AppConfigParam.RSSI_REPORTING, rssi_reporting),
            (AppConfigParam.MAX_NUMBER_OF_MEASUREMENTS, max_number_of_measurements),
        ]
        payload = session_handle.to_bytes(4, "little") + encode_app_config(params)
        message = self._send_command_and_wait_response(
            Gid.SESSION, OidSession.SET_APP_CONFIG, payload
        )
        return parse_app_config_response(message.payload)

    def session_deinit(self, session_handle: int) -> Status:
        """Envia `SESSION_DEINIT`. Payload: session_handle (4 bytes LE).

        `session_handle` es el valor devuelto por `session_init()`, no
        necesariamente el `session_id` que se le paso a ese comando (ver nota
        en `session_init`).
        """
        payload = session_handle.to_bytes(4, "little")
        message = self._send_command_and_wait_response(Gid.SESSION, OidSession.DEINIT, payload)
        return Status(message.payload[0])

    def get_session_state(self, session_handle: int) -> tuple[Status, int]:
        """Envia `SESSION_GET_STATE`. Devuelve `(Status, SessionState)` crudo.

        `session_handle`: ver nota en `session_init`. `SessionState` se
        devuelve como `int`, no como el enum, para tolerar un valor fuera del
        rango confirmado sin lanzar excepcion (mismo criterio que
        `core/models.py` aplica a `SessionStatusNotification.reason_code`).
        """
        payload = session_handle.to_bytes(4, "little")
        message = self._send_command_and_wait_response(Gid.SESSION, OidSession.GET_STATE, payload)
        return Status(message.payload[0]), message.payload[1]

    def get_session_count(self) -> tuple[Status, int]:
        """Envia `SESSION_GET_COUNT`. Devuelve `(Status, cantidad_de_sesiones)`."""
        message = self._send_command_and_wait_response(Gid.SESSION, OidSession.GET_COUNT, b"")
        return Status(message.payload[0]), message.payload[1]

    def ranging_start(self, session_handle: int) -> Status:
        """Envia `RANGING_START`. Payload: session_handle (4 bytes LE).

        Con la sesion configurada (`session_set_app_config`), el firmware
        emite una `RANGING_DATA_NTF` (mismo GID/OID que este comando pero
        `MT=NOTIFICATION`) por cada ronda de ranging -- confirmado contra
        hardware real, incluso sin un segundo dispositivo que responda. Esas
        notificaciones quedan crudas en `UciClient.notifications`: decodificar
        el header con `core.models.parse_ranging_data_notification()`. Las
        mediciones individuales dentro de esa notificacion (que dependen del
        tipo de medicion, p. ej. TWR) no estan implementadas todavia.
        """
        payload = session_handle.to_bytes(4, "little")
        message = self._send_command_and_wait_response(Gid.RANGING, OidRanging.START, payload)
        return Status(message.payload[0])

    def ranging_stop(self, session_handle: int) -> Status:
        """Envia `RANGING_STOP`. Payload: session_handle (4 bytes LE)."""
        payload = session_handle.to_bytes(4, "little")
        message = self._send_command_and_wait_response(Gid.RANGING, OidRanging.STOP, payload)
        return Status(message.payload[0])

    def get_ranging_count(self, session_handle: int) -> tuple[Status, int | None]:
        """Envia `RANGING_GET_COUNT`. Payload: session_handle (4 bytes LE).

        Devuelve `(Status, None)` si `Status != OK`: el conteo de 4 bytes solo
        esta presente en una Response exitosa (confirmado contra `fira.py` del
        SDK, funcion `get_ranging_count`).
        """
        payload = session_handle.to_bytes(4, "little")
        message = self._send_command_and_wait_response(Gid.RANGING, OidRanging.GET_COUNT, payload)
        status = Status(message.payload[0])
        count = int.from_bytes(message.payload[1:5], "little") if status == Status.OK else None
        return status, count
