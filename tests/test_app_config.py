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


REAL_TVS_BLOCK_WITH_STS_KEY_AND_LENGTH = bytes.fromhex(
    "12"
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
    "27 02 08 07"
    "28 06 01 02 03 04 05 06"
    "35 01 01"
)


def test_encode_app_config_matches_real_capture_with_sts_key_and_length() -> None:
    # Igual que test_encode_app_config_matches_real_capture, mas VENDOR_ID,
    # STATIC_STS_IV y STS_LENGTH (conjunto que envia actualmente el cliente).
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
        (AppConfigParam.VENDOR_ID, 0x0708),
        (AppConfigParam.STATIC_STS_IV, 0x060504030201),
        (AppConfigParam.STS_LENGTH, 1),
    ]

    assert encode_app_config(params) == REAL_TVS_BLOCK_WITH_STS_KEY_AND_LENGTH


TVS_BLOCK_WITH_QORVO_REFERENCE_PARITY_PARAMS = bytes.fromhex(
    "19"
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
    "27 02 08 07"
    "28 06 01 02 03 04 05 06"
    "35 01 01"
    "0d 01 01"
    "2e 01 0b"
    "2b 08 00 00 00 00 00 00 00 00"
    "2c 01 00"
    "2d 01 00"
    "13 01 00"
    "32 02 00 00"
)


def test_encode_app_config_matches_qorvo_reference_parity_params() -> None:
    # Igual que test_encode_app_config_matches_real_capture_with_sts_key_and_length,
    # mas los 7 parametros agregados a session_set_app_config para paridad con
    # run_fira_twr.py del SDK (AOA_RESULT_REQ, RESULT_REPORT_CONFIG,
    # UWB_INITIATION_TIME, HOPPING_MODE, BLOCK_STRIDE_LENGTH, RSSI_REPORTING,
    # MAX_NUMBER_OF_MEASUREMENTS). No es una captura de hardware: los
    # tags/anchos vienen de fira_app.py del SDK (ver uci/app_config.py); el
    # bloque completo se computo con esta misma funcion para evitar errores
    # de transcripcion manual.
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
        (AppConfigParam.VENDOR_ID, 0x0708),
        (AppConfigParam.STATIC_STS_IV, 0x060504030201),
        (AppConfigParam.STS_LENGTH, 1),
        (AppConfigParam.AOA_RESULT_REQ, 1),
        (AppConfigParam.RESULT_REPORT_CONFIG, 0x0B),
        (AppConfigParam.UWB_INITIATION_TIME, 0),
        (AppConfigParam.HOPPING_MODE, 0),
        (AppConfigParam.BLOCK_STRIDE_LENGTH, 0),
        (AppConfigParam.RSSI_REPORTING, 0),
        (AppConfigParam.MAX_NUMBER_OF_MEASUREMENTS, 0),
    ]

    assert encode_app_config(params) == TVS_BLOCK_WITH_QORVO_REFERENCE_PARITY_PARAMS


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
