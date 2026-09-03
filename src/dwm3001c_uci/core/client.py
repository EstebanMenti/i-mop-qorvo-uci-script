"""Cliente UCI de alto nivel: comandos del grupo Core, correlacion cmd<->resp.

Ver docs/arquitectura.md Seccion 3.3. Las notificaciones (`MT.NOTIFICATION`)
que llegan mientras se espera una Response no se descartan: se acumulan en
`UciClient.notifications` para que quien las necesite (p. ej. la suite de
validacion, fase F6) pueda inspeccionarlas.
"""

from __future__ import annotations

import time

from dwm3001c_uci.core.errors import UciTimeoutError
from dwm3001c_uci.core.models import DeviceInfo, parse_device_info
from dwm3001c_uci.transport.serial_link import Transport
from dwm3001c_uci.uci.enums import Gid, MessageType, OidCore, Status
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
