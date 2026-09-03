"""Tests de uci/app_config.py (codec TVS de SESSION_SET_APP_CONFIG).

El bloque TVS esperado es exactamente el que se envio contra hardware real
(ver tests/test_core_client.py, REAL_SET_APP_CONFIG_TX).
"""

import pytest

from dwm3001c_uci.uci.app_config import encode_app_config
from dwm3001c_uci.uci.enums import AppConfigParam

REAL_TVS_BLOCK = bytes.fromhex(
    "0f"
    "00 01 01"
    "11 01 01"
    "03 01 00"
    "01 01 02"
    "06 02 00 00"
    "07 02 01 00"
    "04 01 09"
    "02 01 00"
    "12 01 03"
    "22 01 01"
    "14 01 0a"
    "15 01 02"
    "08 02 60 09"
    "09 04 c8 00 00 00"
    "1b 01 19"
)


def test_encode_app_config_matches_real_capture() -> None:
    params: list[tuple[int, int | list[int]]] = [
        (AppConfigParam.DEVICE_TYPE, 1),
        (AppConfigParam.DEVICE_ROLE, 1),
        (AppConfigParam.MULTI_NODE_MODE, 0),
        (AppConfigParam.RANGING_ROUND_USAGE, 2),
        (AppConfigParam.DEVICE_MAC_ADDRESS, 0x0000),
        (AppConfigParam.DST_MAC_ADDRESS, [0x0001]),
        (AppConfigParam.CHANNEL_NUMBER, 9),
        (AppConfigParam.STS_CONFIG, 0),
        (AppConfigParam.RFRAME_CONFIG, 3),
        (AppConfigParam.SCHEDULE_MODE, 1),
        (AppConfigParam.PREAMBLE_CODE_INDEX, 10),
        (AppConfigParam.SFD_ID, 2),
        (AppConfigParam.SLOT_DURATION, 2400),
        (AppConfigParam.RANGING_INTERVAL, 200),
        (AppConfigParam.SLOTS_PER_RR, 25),
    ]

    assert encode_app_config(params) == REAL_TVS_BLOCK


def test_encode_app_config_single_param() -> None:
    encoded = encode_app_config([(AppConfigParam.CHANNEL_NUMBER, 9)])
    assert encoded == bytes.fromhex("01 04 01 09")


def test_encode_app_config_list_value_uses_total_byte_length() -> None:
    # DST_MAC_ADDRESS con 2 direcciones: longitud declarada = 2 elementos * 2 bytes = 4.
    encoded = encode_app_config([(AppConfigParam.DST_MAC_ADDRESS, [0x0001, 0x0002])])
    assert encoded == bytes.fromhex("01 07 04 01 00 02 00")


def test_encode_app_config_rejects_unsupported_param() -> None:
    with pytest.raises(ValueError, match="no soportado"):
        encode_app_config([(0x99, 1)])
