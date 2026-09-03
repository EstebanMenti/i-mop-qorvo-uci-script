"""Protocolo UCI: framing y enums. Modulo puro, sin I/O (ver docs/arquitectura.md 3.2)."""

from dwm3001c_uci.uci.enums import (
    Gid,
    MessageType,
    OidCore,
    OidRanging,
    OidSession,
    OidTest,
    Status,
)
from dwm3001c_uci.uci.framing import (
    MAX_PAYLOAD_SIZE,
    StreamDecoder,
    UciFramingError,
    UciMessage,
    UciPacket,
    decode_packet,
    encode_packet,
    split_into_packets,
)

__all__ = [
    "MAX_PAYLOAD_SIZE",
    "Gid",
    "MessageType",
    "OidCore",
    "OidRanging",
    "OidSession",
    "OidTest",
    "Status",
    "StreamDecoder",
    "UciFramingError",
    "UciMessage",
    "UciPacket",
    "decode_packet",
    "encode_packet",
    "split_into_packets",
]
