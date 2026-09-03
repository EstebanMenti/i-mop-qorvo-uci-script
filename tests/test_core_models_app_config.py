"""Tests de los modelos de AppConfig/Ranging data en core/models.py.

Los payloads son capturas reales contra una placa DWM3001CDK con firmware
UCI, con una sesion configurada (SESSION_SET_APP_CONFIG con el conjunto
minimo, ver docs/protocolo-uci.md) y ranging efectivamente iniciado.
"""

import pytest

from dwm3001c_uci.core.errors import UciPayloadError
from dwm3001c_uci.core.models import (
    AppConfigResult,
    RangingDataNotification,
    RejectedAppConfigParam,
    parse_app_config_response,
    parse_ranging_data_notification,
)
from dwm3001c_uci.uci.enums import RangingMeasType, Status


def test_parse_app_config_response_ok_ignores_trailing_zero_count_byte() -> None:
    # Captura real: cuando Status es OK, el firmware igual manda un segundo
    # byte (count=0), que la Response de fira.py del SDK ni siquiera lee.
    result = parse_app_config_response(bytes.fromhex("00 00"))

    assert result == AppConfigResult(status=Status.OK, rejected=())


def test_parse_app_config_response_ok_without_trailing_byte() -> None:
    result = parse_app_config_response(bytes.fromhex("00"))

    assert result == AppConfigResult(status=Status.OK, rejected=())


def test_parse_app_config_response_with_rejected_params() -> None:
    # Sintetico: Status general SYNTAX_ERROR (0x03), 2 parametros rechazados:
    # param 0x00 con INVALID_PARAM (0x04), param 0x01 con INVALID_RANGE (0x05).
    payload = bytes.fromhex("03 02 00 04 01 05")
    result = parse_app_config_response(payload)

    assert result.status == Status.SYNTAX_ERROR
    assert result.rejected == (
        RejectedAppConfigParam(param=0x00, status=Status.INVALID_PARAM),
        RejectedAppConfigParam(param=0x01, status=Status.INVALID_RANGE),
    )


def test_parse_app_config_response_raises_on_empty_payload() -> None:
    with pytest.raises(UciPayloadError):
        parse_app_config_response(b"")


def test_parse_app_config_response_raises_on_truncated_rejected_list() -> None:
    with pytest.raises(UciPayloadError):
        parse_app_config_response(bytes.fromhex("04 02 00"))  # dice 2 rechazados, solo hay 1 tag


REAL_RANGING_DATA_PAYLOAD = bytes.fromhex(
    "00 00 00 00 01 00 00 00 00 c8 00 00 00 01 00 00 00 00 00 00 00 00 00 00 01 "
    "01 00 21 ff ff ff 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 "
    "00 00 00 00 00 00"
)


def test_parse_ranging_data_notification_header_from_real_capture() -> None:
    notification = parse_ranging_data_notification(REAL_RANGING_DATA_PAYLOAD)

    assert notification == RangingDataNotification(
        sequence_number=0,
        session_handle=1,
        ranging_interval_ms=200,
        measurement_type=RangingMeasType.TWR,
        mac_address_size_bytes=2,
        primary_session_id=0,
        n_measurements=1,
        measurements_raw=REAL_RANGING_DATA_PAYLOAD[25:],
    )


def test_parse_ranging_data_notification_sequence_increments_across_rounds() -> None:
    # Misma estructura, segunda ronda (idx=1) de la misma captura real.
    second_round = bytes.fromhex("01") + REAL_RANGING_DATA_PAYLOAD[1:]
    notification = parse_ranging_data_notification(second_round)

    assert notification.sequence_number == 1
    assert notification.session_handle == 1


def test_parse_ranging_data_notification_raises_on_short_payload() -> None:
    with pytest.raises(UciPayloadError):
        parse_ranging_data_notification(bytes(10))
