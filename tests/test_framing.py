"""Tests del codec de framing UCI (docs/protocolo-uci.md Seccion 1)."""

import pytest

from dwm3001c_uci.uci.enums import Gid, MessageType, OidCore
from dwm3001c_uci.uci.framing import (
    MAX_PAYLOAD_SIZE,
    StreamDecoder,
    UciFramingError,
    UciMessage,
    UciPacket,
    decode_packet,
    encode_packet,
    split_into_packets,
    try_decode_packet,
)


def test_encode_command_without_payload() -> None:
    # CORE_GET_DEVICE_INFO (GID=0x00, OID=0x02), Command, sin payload.
    packet = UciPacket(
        mt=MessageType.COMMAND, pbf=False, gid=Gid.CORE, oid=OidCore.GET_DEVICE_INFO, payload=b""
    )
    encoded = encode_packet(packet)
    assert encoded == bytes([0x20, 0x02, 0x00, 0x00])


def test_encode_response_with_payload() -> None:
    # Response (MT=2) a CORE_GET_DEVICE_INFO, con 2 bytes de payload.
    packet = UciPacket(
        mt=MessageType.RESPONSE,
        pbf=False,
        gid=Gid.CORE,
        oid=OidCore.GET_DEVICE_INFO,
        payload=b"\xab\xcd",
    )
    encoded = encode_packet(packet)
    assert encoded == bytes([0x40, 0x02, 0x00, 0x02, 0xAB, 0xCD])


def test_decode_roundtrip() -> None:
    original = UciPacket(
        mt=MessageType.NOTIFICATION,
        pbf=False,
        gid=Gid.CORE,
        oid=OidCore.DEVICE_STATUS_NTF,
        payload=b"\x01",
    )
    decoded = decode_packet(encode_packet(original))
    assert decoded == original


def test_pbf_bit_is_encoded_and_decoded() -> None:
    original = UciPacket(
        mt=MessageType.RESPONSE, pbf=True, gid=Gid.CORE, oid=OidCore.GET_CAPS, payload=b"\x01\x02"
    )
    decoded = decode_packet(encode_packet(original))
    assert decoded.pbf is True


def test_data_packet_uses_16_bit_length() -> None:
    payload = bytes(300)  # excede el limite de 1 byte, valido para Data Packet (MT=0).
    packet = UciPacket(mt=MessageType.DATA_PACKET, pbf=False, gid=0x00, oid=0x00, payload=payload)
    encoded = encode_packet(packet)
    assert encoded[2] == 300 & 0xFF
    assert encoded[3] == (300 >> 8) & 0xFF
    decoded = decode_packet(encoded)
    assert decoded.payload == payload


def test_command_payload_over_max_size_is_rejected() -> None:
    with pytest.raises(UciFramingError):
        UciPacket(
            mt=MessageType.COMMAND,
            pbf=False,
            gid=Gid.CORE,
            oid=OidCore.SET_CONFIG,
            payload=bytes(MAX_PAYLOAD_SIZE + 1),
        )


def test_try_decode_returns_none_on_incomplete_header() -> None:
    assert try_decode_packet(b"\x20\x02") is None


def test_try_decode_returns_none_on_incomplete_payload() -> None:
    # Header dice 2 bytes de payload, pero solo llego 1.
    incomplete = bytes([0x40, 0x02, 0x00, 0x02, 0xAB])
    assert try_decode_packet(incomplete) is None


def test_decode_packet_raises_on_trailing_bytes() -> None:
    valid = encode_packet(
        UciPacket(mt=MessageType.COMMAND, pbf=False, gid=Gid.CORE, oid=OidCore.RESET, payload=b"")
    )
    with pytest.raises(UciFramingError):
        decode_packet(valid + b"\x00")


def test_decode_packet_raises_on_unknown_message_type() -> None:
    # MT invalido: no hay valor 4-7 definido en MessageType actualmente, pero el
    # campo tiene 3 bits (0-7). Se prueba con un valor fuera del enum (ej. 7).
    header = bytes([(7 << 5) | 0x00, 0x00, 0x00, 0x00])
    with pytest.raises(UciFramingError):
        try_decode_packet(header)


def test_split_into_packets_single_chunk() -> None:
    packets = split_into_packets(MessageType.COMMAND, Gid.CORE, OidCore.SET_CONFIG, b"\x01\x02")
    assert len(packets) == 1
    assert packets[0].pbf is False


def test_split_into_packets_fragments_large_payload() -> None:
    payload = bytes(range(256)) * 2  # 512 bytes, > MAX_PAYLOAD_SIZE
    packets = split_into_packets(
        MessageType.COMMAND, Gid.CORE, OidCore.SET_CONFIG, payload, max_payload=200
    )
    assert len(packets) == 3
    assert all(p.pbf for p in packets[:-1])
    assert packets[-1].pbf is False
    assert b"".join(p.payload for p in packets) == payload


def test_split_into_packets_empty_payload_yields_single_final_packet() -> None:
    packets = split_into_packets(MessageType.COMMAND, Gid.CORE, OidCore.RESET, b"")
    assert packets == [
        UciPacket(mt=MessageType.COMMAND, pbf=False, gid=Gid.CORE, oid=OidCore.RESET, payload=b"")
    ]


def test_stream_decoder_reassembles_single_packet_message() -> None:
    decoder = StreamDecoder()
    raw = encode_packet(
        UciPacket(
            mt=MessageType.RESPONSE,
            pbf=False,
            gid=Gid.CORE,
            oid=OidCore.GET_DEVICE_INFO,
            payload=b"\x01\x02",
        )
    )
    messages = decoder.feed(raw)
    assert messages == [
        UciMessage(
            mt=MessageType.RESPONSE, gid=Gid.CORE, oid=OidCore.GET_DEVICE_INFO, payload=b"\x01\x02"
        )
    ]


def test_stream_decoder_reassembles_fragmented_message() -> None:
    decoder = StreamDecoder()
    payload = bytes(range(256)) * 2
    fragments = split_into_packets(
        MessageType.RESPONSE, Gid.CORE, OidCore.GET_CAPS, payload, max_payload=200
    )
    raw = b"".join(encode_packet(p) for p in fragments)

    messages = decoder.feed(raw)

    assert len(messages) == 1
    assert messages[0].payload == payload
    assert messages[0].gid == Gid.CORE
    assert messages[0].oid == OidCore.GET_CAPS


def test_stream_decoder_handles_partial_bytes_across_feed_calls() -> None:
    decoder = StreamDecoder()
    raw = encode_packet(
        UciPacket(
            mt=MessageType.COMMAND,
            pbf=False,
            gid=Gid.CORE,
            oid=OidCore.RESET,
            payload=b"\x01\x02\x03",
        )
    )

    assert decoder.feed(raw[:2]) == []
    assert decoder.feed(raw[2:5]) == []
    messages = decoder.feed(raw[5:])

    assert len(messages) == 1
    assert messages[0].payload == b"\x01\x02\x03"


def test_stream_decoder_parses_multiple_messages_in_one_feed() -> None:
    decoder = StreamDecoder()
    first = encode_packet(
        UciPacket(mt=MessageType.RESPONSE, pbf=False, gid=Gid.CORE, oid=OidCore.RESET, payload=b"")
    )
    second = encode_packet(
        UciPacket(
            mt=MessageType.NOTIFICATION,
            pbf=False,
            gid=Gid.CORE,
            oid=OidCore.DEVICE_STATUS_NTF,
            payload=b"\x01",
        )
    )

    messages = decoder.feed(first + second)

    assert len(messages) == 2
    assert messages[0].oid == OidCore.RESET
    assert messages[1].oid == OidCore.DEVICE_STATUS_NTF


def test_stream_decoder_raises_on_interrupted_fragment() -> None:
    decoder = StreamDecoder()
    fragment_a = UciPacket(
        mt=MessageType.RESPONSE, pbf=True, gid=Gid.CORE, oid=OidCore.GET_CAPS, payload=b"\x01"
    )
    interrupting = UciPacket(
        mt=MessageType.NOTIFICATION,
        pbf=False,
        gid=Gid.CORE,
        oid=OidCore.DEVICE_STATUS_NTF,
        payload=b"\x00",
    )

    with pytest.raises(UciFramingError):
        decoder.feed(encode_packet(fragment_a) + encode_packet(interrupting))
