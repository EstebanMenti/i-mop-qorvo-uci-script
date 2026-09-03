"""Cliente UCI de alto nivel: comandos del grupo Core, correlacion cmd<->resp.

Ver docs/arquitectura.md Seccion 3.3. Las notificaciones (`MT.NOTIFICATION`)
que llegan mientras se espera una Response no se descartan: se acumulan en
`UciClient.notifications` para que quien las necesite (p. ej. la suite de
validacion, fase F6) pueda inspeccionarlas.
"""

from __future__ import annotations

import time

from dwm3001c_uci.core.errors import UciTimeoutError
from dwm3001c_uci.core.models import (
    DeviceInfo,
    SessionInitResult,
    parse_device_info,
    parse_session_init_result,
)
from dwm3001c_uci.transport.serial_link import Transport
from dwm3001c_uci.uci.enums import Gid, MessageType, OidCore, OidSession, SessionType, Status
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
