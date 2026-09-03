"""Framing UCI: codificacion/decodificacion de tramas y reensamblado de mensajes.

Formato de encabezado (docs/protocolo-uci.md Seccion 1):

    Byte 0: MT(3 bits) << 5 | PBF(1 bit) << 4 | GID(4 bits)
    Byte 1: OID (1 byte)
    Byte 2: RFU (0x00), salvo Data Packet (MT=0): byte 2-3 = longitud (16 bits LE)
    Byte 3: longitud del payload (1 byte), salvo Data Packet
    Bytes 4..: payload

Modulo puro: no realiza I/O, no conoce el transporte (ver docs/arquitectura.md
Seccion 3.2). El tamano maximo de payload por paquete (255 bytes) se deriva del
campo de longitud de 1 byte para Command/Response/Notification -- es una
restriccion estructural del framing, no un valor de implementacion arbitrario.
"""

from __future__ import annotations

from dataclasses import dataclass

from dwm3001c_uci.uci.enums import MessageType

HEADER_SIZE = 4
MAX_PAYLOAD_SIZE = 255
"""Payload maximo por paquete fisico para MT != DATA_PACKET (campo de longitud de 1 byte)."""


class UciFramingError(Exception):
    """Error de framing: header invalido, RFU inesperado, o fragmentos inconsistentes."""


@dataclass(frozen=True)
class UciPacket:
    """Un paquete fisico UCI (una trama tal como viaja por el transporte)."""

    mt: MessageType
    pbf: bool
    gid: int
    oid: int
    payload: bytes

    def __post_init__(self) -> None:
        if not 0 <= self.gid <= 0x0F:
            raise UciFramingError(f"GID fuera de rango: 0x{self.gid:X}")
        if not 0 <= self.oid <= 0xFF:
            raise UciFramingError(f"OID fuera de rango: 0x{self.oid:X}")
        if self.mt != MessageType.DATA_PACKET and len(self.payload) > MAX_PAYLOAD_SIZE:
            raise UciFramingError(
                f"payload de {len(self.payload)} bytes excede el maximo de "
                f"{MAX_PAYLOAD_SIZE} bytes por paquete para MT={self.mt.name}"
            )


@dataclass(frozen=True)
class UciMessage:
    """Un mensaje logico UCI ya reensamblado (payload completo, sin fragmentar)."""

    mt: MessageType
    gid: int
    oid: int
    payload: bytes


def encode_packet(packet: UciPacket) -> bytes:
    """Codifica un :class:`UciPacket` a los bytes de una trama fisica."""
    byte0 = (int(packet.mt) << 5) | ((1 if packet.pbf else 0) << 4) | (packet.gid & 0x0F)
    byte1 = packet.oid & 0xFF
    if packet.mt == MessageType.DATA_PACKET:
        length = len(packet.payload)
        header = bytes([byte0, byte1, length & 0xFF, (length >> 8) & 0xFF])
    else:
        header = bytes([byte0, byte1, 0x00, len(packet.payload) & 0xFF])
    return header + packet.payload


def try_decode_packet(buffer: bytes) -> tuple[UciPacket, int] | None:
    """Intenta decodificar un paquete desde el inicio de ``buffer``.

    Devuelve ``(paquete, bytes_consumidos)`` si ``buffer`` contiene al menos un
    paquete completo, o ``None`` si hay que esperar mas bytes. No lanza
    excepcion por datos insuficientes -- es el mecanismo normal de un parser de
    stream (ver :class:`StreamDecoder`).
    """
    if len(buffer) < HEADER_SIZE:
        return None

    byte0, byte1 = buffer[0], buffer[1]
    mt_value = (byte0 >> 5) & 0x07
    pbf = bool((byte0 >> 4) & 0x01)
    gid = byte0 & 0x0F
    oid = byte1

    try:
        mt = MessageType(mt_value)
    except ValueError as exc:
        raise UciFramingError(f"MT desconocido: 0x{mt_value:X}") from exc

    if mt == MessageType.DATA_PACKET:
        length = buffer[2] | (buffer[3] << 8)
    else:
        length = buffer[3]

    total_size = HEADER_SIZE + length
    if len(buffer) < total_size:
        return None

    payload = bytes(buffer[HEADER_SIZE:total_size])
    packet = UciPacket(mt=mt, pbf=pbf, gid=gid, oid=oid, payload=payload)
    return packet, total_size


def decode_packet(buffer: bytes) -> UciPacket:
    """Decodifica exactamente un paquete completo desde ``buffer`` (sin sobrantes).

    Pensado para tests y para decodificar una trama ya delimitada por fuera
    (p. ej. una fixture). Para un stream continuo de bytes, usar
    :class:`StreamDecoder`.
    """
    result = try_decode_packet(buffer)
    if result is None:
        raise UciFramingError(f"buffer incompleto: {len(buffer)} bytes no forman un paquete")
    packet, consumed = result
    if consumed != len(buffer):
        raise UciFramingError(
            f"quedan {len(buffer) - consumed} bytes sin consumir despues del paquete"
        )
    return packet


def split_into_packets(
    mt: MessageType, gid: int, oid: int, payload: bytes, max_payload: int = MAX_PAYLOAD_SIZE
) -> list[UciPacket]:
    """Fragmenta ``payload`` en uno o mas :class:`UciPacket`, seteando `PBF`.

    Todos los paquetes salvo el ultimo llevan ``pbf=True``. Si ``payload`` cabe
    en un solo paquete, devuelve una lista de un elemento con ``pbf=False``.
    """
    if not payload:
        return [UciPacket(mt=mt, pbf=False, gid=gid, oid=oid, payload=b"")]

    chunks = [payload[i : i + max_payload] for i in range(0, len(payload), max_payload)]
    last_index = len(chunks) - 1
    return [
        UciPacket(mt=mt, pbf=(index != last_index), gid=gid, oid=oid, payload=chunk)
        for index, chunk in enumerate(chunks)
    ]


class StreamDecoder:
    """Reensambla un stream continuo de bytes en mensajes UCI completos.

    Uso previsto: alimentar con los bytes leidos del transporte (``feed``) y
    consumir los :class:`UciMessage` completos que vayan quedando listos.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        # Acumulador de fragmentos en progreso: UciMessage, no UciPacket, porque
        # el payload acumulado puede superar MAX_PAYLOAD_SIZE (esa cota aplica a
        # un paquete fisico, no al mensaje logico reensamblado).
        self._pending: UciMessage | None = None

    def feed(self, data: bytes) -> list[UciMessage]:
        """Agrega bytes recibidos y devuelve los mensajes que quedaron completos."""
        self._buffer.extend(data)
        messages: list[UciMessage] = []

        while True:
            result = try_decode_packet(bytes(self._buffer))
            if result is None:
                break
            packet, consumed = result
            del self._buffer[:consumed]

            message = self._accumulate(packet)
            if message is not None:
                messages.append(message)

        return messages

    def _accumulate(self, packet: UciPacket) -> UciMessage | None:
        if self._pending is not None:
            if (self._pending.gid, self._pending.oid, self._pending.mt) != (
                packet.gid,
                packet.oid,
                packet.mt,
            ):
                raise UciFramingError(
                    "paquete fragmentado interrumpido por uno de un GID/OID/MT distinto"
                )
            merged_payload = self._pending.payload + packet.payload
        else:
            merged_payload = packet.payload

        message = UciMessage(mt=packet.mt, gid=packet.gid, oid=packet.oid, payload=merged_payload)

        if packet.pbf:
            self._pending = message
            return None

        self._pending = None
        return message
