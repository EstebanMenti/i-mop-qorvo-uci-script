"""Ranging mixto: placa local UCI (USB) + placa remota CLI (BLE via el puente
nRF52840, `I-mop-nrf52840-fw`).

**Experimental.** Arquitectonicamente, CLI y UCI son dos interfaces de host
sobre el mismo motor FiRa/MAC/PHY ("uwb-stack") del chip Qorvo -- confirmado
contra el Developer Manual del SDK (ver docs/plan-implementacion.md, "Nota:
el puente BLE del proyecto hermano..."). Este modulo prueba si eso alcanza
para que dos placas con firmwares e interfaces de control distintas
completen un ranging real por aire; no hay garantia previa (ni de Qorvo ni de
ningun repo de este proyecto) de que esto funcione.

**La distancia se mide del lado UCI** (`RANGING_DATA_NTF` -> `TwrMeasurement`),
no del lado CLI: el puente BLE es estrictamente petición/respuesta y **no
reenvia las notificaciones asincronas** (`SESSION_INFO_NTF`) que el Qorvo
remoto emite sin haber sido consultado -- ver
`I-mop-nrf52840-fw/doc/00_BLE_Protocol_Specification.md` Seccion 7.6,
"Limitacion conocida de este diseño".

Roles fijos de este script: la placa local (UCI) es Controller/Initiator
(direccion `0x0000`), la placa remota (CLI, via el bridge) es Controlee/
Responder (direccion `0x0001`) -- coincide con los valores por defecto de
`RESPF` en el Qorvo (`ADDR=1, PADDR=0`).
"""

from __future__ import annotations

import argparse
import logging
import time

from dwm3001c_uci.cli_bridge.ble_transport import BleShellTransport
from dwm3001c_uci.cli_bridge.client import CliBridgeClient
from dwm3001c_uci.cli_bridge.errors import BleShellError, CliBridgeError
from dwm3001c_uci.core.client import UciClient
from dwm3001c_uci.core.models import parse_ranging_data_notification, parse_twr_measurement
from dwm3001c_uci.transport.serial_link import SerialLink
from dwm3001c_uci.uci.enums import DeviceRole, DeviceType, SessionType, Status

logger = logging.getLogger(__name__)

LOCAL_DEVICE_MAC_ADDRESS = 0x0000
REMOTE_DEVICE_MAC_ADDRESS = 0x0001


def run_mixed_ranging(
    *,
    local_port: str,
    remote_ble_name: str,
    channel: int = 9,
    preamble_code_index: int = 10,
    session_id: int = 1,
    duration_s: float = 6.0,
    poll_interval_s: float = 0.2,
) -> int:
    """Arma Controller(UCI, local)/Responder(CLI, remota) y cuenta rondas exitosas.

    Devuelve la cantidad de rondas con `TwrMeasurement.status == Status.OK`
    (medicion real de distancia) observadas del lado UCI durante `duration_s`.
    """
    with SerialLink(local_port) as link:
        uci = UciClient(link)
        uci.reset()

        transport = BleShellTransport()
        bridge = CliBridgeClient(transport)
        handle: int | None = None
        try:
            logger.info("Conectando al puente BLE %r...", remote_ble_name)
            address = bridge.connect(remote_ble_name)
            logger.info("Conectado al puente BLE: %s", address)

            logger.info("Encendiendo el modulo Qorvo remoto (qorvo on)...")
            bridge.power_on()

            logger.info("STAT remoto: %s", bridge.stat())

            logger.info("Deteniendo cualquier aplicacion FiRa remota previa (STOP)...")
            bridge.stop()

            logger.info("Configurando responder remoto (RESPF)...")
            respf_output = bridge.respf(
                CHAN=channel,
                PCODE=preamble_code_index,
                RRU="DSTWR",
                ADDR=REMOTE_DEVICE_MAC_ADDRESS,
                PADDR=LOCAL_DEVICE_MAC_ADDRESS,
            )
            logger.info("RESPF remoto:\n%s", respf_output)

            logger.info("Inicializando sesion local (UCI, Controller/Initiator)...")
            init_result = uci.session_init(session_id=session_id, session_type=SessionType.RANGING)
            handle = init_result.session_handle
            logger.info("session_handle local: %s", handle)

            config_result = uci.session_set_app_config(
                handle,
                device_type=DeviceType.CONTROLLER,
                device_role=DeviceRole.INITIATOR,
                device_mac_address=LOCAL_DEVICE_MAC_ADDRESS,
                dst_mac_addresses=[REMOTE_DEVICE_MAC_ADDRESS],
                channel_number=channel,
                preamble_code_index=preamble_code_index,
            )
            if config_result.status != Status.OK:
                raise RuntimeError(
                    f"session_set_app_config local fallo: {config_result.status.name}, "
                    f"rechazados={config_result.rejected}"
                )

            logger.info("Iniciando ranging local (RANGING_START)...")
            start_status = uci.ranging_start(handle)
            if start_status != Status.OK:
                raise RuntimeError(f"ranging_start local fallo: {start_status.name}")

            successful_rounds = 0
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline:
                # uci.poll_notifications(), no time.sleep(): UciClient no tiene
                # ningun hilo de fondo leyendo el puerto -- sin esto, casi
                # ninguna RANGING_DATA_NTF espontanea se procesaria (ver
                # docstring de poll_notifications en core/client.py).
                pending = uci.poll_notifications(poll_interval_s)
                for notification in pending:
                    if notification.gid != 0x02 or notification.oid != 0x00:
                        continue
                    data = parse_ranging_data_notification(notification.payload)
                    if data.n_measurements < 1:
                        continue
                    twr = parse_twr_measurement(data.measurements_raw, data.mac_address_size_bytes)
                    is_success = twr.status == Status.OK
                    if is_success:
                        successful_rounds += 1
                    logger.info(
                        "Ronda %s: mac=%s status=%s%s",
                        data.sequence_number,
                        twr.mac_address,
                        twr.status.name,
                        f" distancia={twr.distance_cm}cm" if is_success else "",
                    )

            logger.info("Deteniendo ranging local...")
            uci.ranging_stop(handle)

        finally:
            try:
                if handle is not None:
                    uci.session_deinit(handle)
            finally:
                try:
                    bridge.stop()
                except (BleShellError, CliBridgeError) as exc:
                    logger.warning("No se pudo detener la aplicacion remota al finalizar: %s", exc)
                try:
                    # Placa remota a bateria, compartida: no dejarla encendida
                    # innecesariamente al terminar (ver CliBridgeClient.power_off).
                    bridge.power_off()
                except (BleShellError, CliBridgeError) as exc:
                    logger.warning("No se pudo apagar el modulo remoto al finalizar: %s", exc)
                transport.close()

    logger.info("Rondas con medicion exitosa: %d", successful_rounds)
    return successful_rounds


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-port", required=True, help="Puerto COM de la placa UCI local")
    parser.add_argument(
        "--remote-ble-name",
        required=True,
        help="Nombre (substring, p. ej. 'UWB-Node-2') o direccion BLE del puente remoto",
    )
    parser.add_argument("--channel", type=int, default=9)
    parser.add_argument("--preamble-code-index", type=int, default=10)
    parser.add_argument("--duration-s", type=float, default=6.0)
    args = parser.parse_args()

    successful_rounds = run_mixed_ranging(
        local_port=args.local_port,
        remote_ble_name=args.remote_ble_name,
        channel=args.channel,
        preamble_code_index=args.preamble_code_index,
        duration_s=args.duration_s,
    )
    print(f"Rondas con medicion exitosa: {successful_rounds}")


if __name__ == "__main__":
    main()
