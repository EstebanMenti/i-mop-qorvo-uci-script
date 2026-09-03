"""Tests de los modelos de Session en core/models.py.

Los payloads usados son capturas reales contra una placa DWM3001CDK con
firmware UCI (session_id=1, SessionType.RANGING), no valores sinteticos.
"""

import pytest

from dwm3001c_uci.core.errors import UciPayloadError
from dwm3001c_uci.core.models import (
    SessionInitResult,
    SessionStatusNotification,
    parse_session_init_result,
    parse_session_status_notification,
)
from dwm3001c_uci.uci.enums import SessionState, Status, session_state_change_reason_name


def test_parse_session_init_result_from_real_capture() -> None:
    # Response real de SESSION_INIT (payload sin el header de trama).
    payload = bytes.fromhex("00 01 00 00 00")

    result = parse_session_init_result(payload)

    assert result == SessionInitResult(status=Status.OK, session_handle=1)


def test_parse_session_init_result_raises_on_short_payload() -> None:
    with pytest.raises(UciPayloadError):
        parse_session_init_result(bytes.fromhex("00 01"))


def test_parse_session_status_notification_init_from_real_capture() -> None:
    # SESSION_STATUS_NTF real emitida tras SESSION_INIT.
    payload = bytes.fromhex("01 00 00 00 00 00")

    notification = parse_session_status_notification(payload)

    assert notification == SessionStatusNotification(
        session_id=1, state=SessionState.INIT, reason_code=0
    )
    assert (
        session_state_change_reason_name(notification.reason_code)
        == "STATE_CHANGE_WITH_SESSION_MANAGEMENT_COMMANDS"
    )


def test_parse_session_status_notification_deinit_from_real_capture() -> None:
    # SESSION_STATUS_NTF real emitida tras SESSION_DEINIT.
    payload = bytes.fromhex("01 00 00 00 01 00")

    notification = parse_session_status_notification(payload)

    assert notification.state == SessionState.DEINIT


def test_parse_session_status_notification_raises_on_short_payload() -> None:
    with pytest.raises(UciPayloadError):
        parse_session_status_notification(bytes.fromhex("01 00 00"))


def test_session_state_change_reason_name_unknown_value_does_not_raise() -> None:
    assert session_state_change_reason_name(0x99) == "UNKNOWN_REASON(0x99)"
