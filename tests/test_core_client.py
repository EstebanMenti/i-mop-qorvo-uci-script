"""Tests de core/client.py (UciClient).

Los bytes de TX/RX usados como fixture son una captura real contra una placa
DWM3001CDK con firmware UCI (release QM33SDK-1.1.1, ver docs/protocolo-uci.md),
no valores sinteticos inventados.
"""

import pytest

from dwm3001c_uci.core.client import UciClient
from dwm3001c_uci.core.errors import UciTimeoutError
from dwm3001c_uci.uci.enums import (
    DeviceRole,
    DeviceType,
    SessionState,
    SessionType,
    Status,
)
from tests.fakes import FakeTransport

# CORE_GET_DEVICE_INFO: TX real y RX real (1 sola Response, sin notificaciones).
# El payload es exactamente el mismo verificado en test_core_models.py
# (REAL_DEVICE_INFO_PAYLOAD), con el header de trama real antepuesto.
REAL_GET_DEVICE_INFO_TX = bytes.fromhex("20 02 00 00")
REAL_GET_DEVICE_INFO_PAYLOAD = bytes.fromhex(
    "00 02 00 02 00 02 00 01 10 34 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "50 56 34 58 32 30 0e e0 ca 09 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 00 02 03 ca de 00"
)
REAL_GET_DEVICE_INFO_RX = bytes.fromhex("40 02 00 3e") + REAL_GET_DEVICE_INFO_PAYLOAD

# CORE_RESET (payload 0x00): TX real y RX real, con 2 CORE_DEVICE_STATUS_NTF
# intercaladas (una antes y otra despues de la Response) tal como las emitio
# el firmware real.
REAL_RESET_TX = bytes.fromhex("20 00 00 01 00")
REAL_RESET_RX = bytes.fromhex("60 01 00 01 01 40 00 00 01 00 60 01 00 01 01")


def test_get_device_info_sends_expected_command_and_parses_real_response() -> None:
    transport = FakeTransport(rx_data=REAL_GET_DEVICE_INFO_RX)
    client = UciClient(transport)

    info = client.get_device_info()

    assert transport.tx_log == [REAL_GET_DEVICE_INFO_TX]
    assert info.status == Status.OK
    assert str(info.uci_version) == "2.0.0"
    assert str(info.uci_test_version) == "1.1.0"


def test_reset_sends_expected_command_and_returns_ok() -> None:
    transport = FakeTransport(rx_data=REAL_RESET_RX)
    client = UciClient(transport)

    status = client.reset()

    assert transport.tx_log == [REAL_RESET_TX]
    assert status == Status.OK


def test_reset_captures_interleaved_notifications_instead_of_dropping_them() -> None:
    transport = FakeTransport(rx_data=REAL_RESET_RX)
    client = UciClient(transport)

    client.reset()

    assert len(client.notifications) == 2
    assert all(n.gid == 0x00 and n.oid == 0x01 for n in client.notifications)
    assert all(n.payload == b"\x01" for n in client.notifications)


def test_send_command_raises_timeout_when_device_never_responds() -> None:
    transport = FakeTransport(rx_data=b"")
    client = UciClient(transport, timeout_s=0.05)

    with pytest.raises(UciTimeoutError):
        client.reset()


# CORE_GET_CAPS: TX real y RX real. El payload de capacidades (lista TLV) no
# se decodifica todavia (ver docs/plan-implementacion.md F3): este test solo
# verifica el mecanismo de correlacion y que el status/remaining se separen bien.
REAL_GET_CAPS_TX = bytes.fromhex("20 03 00 00")
REAL_GET_CAPS_RX = bytes.fromhex(
    "40 03 00 5e 00 1a 00 02 03 01 01 02 ff 00 02 04 02 00 02 00 03 04 02 00 02 00 "
    "04 01 03 05 02 03 00 06 02 1e 00 07 01 19 08 01 03 09 01 02 0a 01 02 0b 01 01 "
    "0c 01 01 0d 01 01 0e 01 09 0f 01 0a 10 01 01 11 01 3f 12 05 00 00 00 00 00 13 "
    "01 00 14 01 00 15 01 00 16 01 02 17 01 00 18 01 00 19 01 00"
)


def test_get_caps_raw_returns_status_and_remaining_payload() -> None:
    transport = FakeTransport(rx_data=REAL_GET_CAPS_RX)
    client = UciClient(transport)

    status, remaining = client.get_caps_raw()

    assert transport.tx_log == [REAL_GET_CAPS_TX]
    assert status == Status.OK
    assert len(remaining) == 93


# Grupo Session: TX/RX reales, capturados pidiendo session_id=7. El firmware
# asigno session_handle=1 (distinto del id pedido - ver docs/protocolo-uci.md
# Seccion 2.1), asi que las llamadas siguientes usan ese handle=1.
REAL_SESSION_INIT_TX = bytes.fromhex("21 00 00 05 07 00 00 00 00")
REAL_SESSION_INIT_RX = bytes.fromhex("41 00 00 05 00 01 00 00 00 61 02 00 06 01 00 00 00 00 00")
REAL_SESSION_GET_STATE_TX = bytes.fromhex("21 06 00 04 01 00 00 00")
REAL_SESSION_GET_STATE_RX = bytes.fromhex("41 06 00 02 00 00")
REAL_SESSION_GET_COUNT_TX = bytes.fromhex("21 05 00 00")
REAL_SESSION_GET_COUNT_ACTIVE_RX = bytes.fromhex("41 05 00 02 00 01")
REAL_SESSION_GET_COUNT_EMPTY_RX = bytes.fromhex("41 05 00 02 00 00")
REAL_SESSION_DEINIT_TX = bytes.fromhex("21 01 00 04 01 00 00 00")
REAL_SESSION_DEINIT_RX = bytes.fromhex("41 01 00 01 00 61 02 00 06 01 00 00 00 01 00")


def test_session_init_sends_expected_command_and_returns_real_handle() -> None:
    transport = FakeTransport(rx_data=REAL_SESSION_INIT_RX)
    client = UciClient(transport)

    result = client.session_init(session_id=7, session_type=SessionType.RANGING)

    assert transport.tx_log == [REAL_SESSION_INIT_TX]
    assert result.status == Status.OK
    # El handle real (1) difiere del session_id pedido (7): hallazgo confirmado
    # contra hardware, ver docs/protocolo-uci.md Seccion 2.1.
    assert result.session_handle == 1


def test_session_init_captures_session_status_notification() -> None:
    transport = FakeTransport(rx_data=REAL_SESSION_INIT_RX)
    client = UciClient(transport)

    client.session_init(session_id=7, session_type=SessionType.RANGING)

    assert len(client.notifications) == 1
    notification = client.notifications[0]
    assert notification.gid == 0x01
    assert notification.oid == 0x02
    assert notification.payload == bytes.fromhex("01 00 00 00 00 00")


def test_get_session_state_uses_handle_not_original_session_id() -> None:
    transport = FakeTransport(rx_data=REAL_SESSION_GET_STATE_RX)
    client = UciClient(transport)

    status, state = client.get_session_state(session_handle=1)

    assert transport.tx_log == [REAL_SESSION_GET_STATE_TX]
    assert status == Status.OK
    assert SessionState(state) == SessionState.INIT


def test_get_session_count_reflects_active_and_then_empty() -> None:
    transport = FakeTransport(rx_data=REAL_SESSION_GET_COUNT_ACTIVE_RX)
    client = UciClient(transport)
    assert client.get_session_count() == (Status.OK, 1)

    transport_empty = FakeTransport(rx_data=REAL_SESSION_GET_COUNT_EMPTY_RX)
    client_empty = UciClient(transport_empty)
    assert client_empty.get_session_count() == (Status.OK, 0)


def test_session_deinit_sends_expected_command_and_captures_notification() -> None:
    transport = FakeTransport(rx_data=REAL_SESSION_DEINIT_RX)
    client = UciClient(transport)

    status = client.session_deinit(session_handle=1)

    assert transport.tx_log == [REAL_SESSION_DEINIT_TX]
    assert status == Status.OK
    assert len(client.notifications) == 1
    assert client.notifications[0].payload == bytes.fromhex("01 00 00 00 01 00")


# Grupo Ranging: TX/RX reales contra una sesion creada pero NUNCA configurada
# con SESSION_SET_APP_CONFIG (ese comando todavia no esta implementado, ver
# docs/plan-implementacion.md F4). Por eso RANGING_START/STOP devuelven
# Status.ERROR_SESSION_NOT_CONFIGURED en vez de arrancar un ranging real: es
# el resultado esperado y confirmado, no un caso de error inventado.
REAL_RANGING_GET_COUNT_TX = bytes.fromhex("22 03 00 04 01 00 00 00")
REAL_RANGING_GET_COUNT_RX = bytes.fromhex("42 03 00 05 00 00 00 00 00")
REAL_RANGING_START_TX = bytes.fromhex("22 00 00 04 01 00 00 00")
REAL_RANGING_START_RX = bytes.fromhex("42 00 00 01 15")
REAL_RANGING_STOP_TX = bytes.fromhex("22 01 00 04 01 00 00 00")
REAL_RANGING_STOP_RX = bytes.fromhex("42 01 00 01 15")


def test_get_ranging_count_returns_status_and_count_on_success() -> None:
    transport = FakeTransport(rx_data=REAL_RANGING_GET_COUNT_RX)
    client = UciClient(transport)

    status, count = client.get_ranging_count(session_handle=1)

    assert transport.tx_log == [REAL_RANGING_GET_COUNT_TX]
    assert status == Status.OK
    assert count == 0


def test_get_ranging_count_returns_none_when_status_is_not_ok() -> None:
    # Response sintetica: Status distinto de OK no trae los 4 bytes de conteo.
    transport = FakeTransport(rx_data=bytes.fromhex("42 03 00 01 15"))
    client = UciClient(transport)

    status, count = client.get_ranging_count(session_handle=1)

    assert status == Status.ERROR_SESSION_NOT_CONFIGURED
    assert count is None


def test_ranging_start_on_unconfigured_session_returns_real_error_status() -> None:
    transport = FakeTransport(rx_data=REAL_RANGING_START_RX)
    client = UciClient(transport)

    status = client.ranging_start(session_handle=1)

    assert transport.tx_log == [REAL_RANGING_START_TX]
    assert status == Status.ERROR_SESSION_NOT_CONFIGURED


def test_ranging_stop_sends_expected_command() -> None:
    transport = FakeTransport(rx_data=REAL_RANGING_STOP_RX)
    client = UciClient(transport)

    status = client.ranging_stop(session_handle=1)

    assert transport.tx_log == [REAL_RANGING_STOP_TX]
    assert status == Status.ERROR_SESSION_NOT_CONFIGURED


# SESSION_SET_APP_CONFIG con el conjunto minimo de parametros (18, incluidos
# VENDOR_ID/STATIC_STS_IV/STS_LENGTH para interoperar con el perfil BPRF4 por
# defecto del firmware CLI), y RANGING_START ya con la sesion configurada:
# capturas reales contra hardware, session_handle=1. A diferencia de los
# fixtures de arriba (sesion nunca configurada), aca RANGING_START devuelve
# Status.OK y el firmware emite RANGING_DATA_NTF real.
REAL_SET_APP_CONFIG_TX = bytes.fromhex(
    "21 03 00 47 01 00 00 00 12 00 01 01 11 01 01 03 01 00 01 01 02 06 02 00 00 "
    "07 02 01 00 04 01 09 02 01 00 12 01 03 22 01 01 14 01 0a 15 01 02 08 02 60 "
    "09 09 04 c8 00 00 00 1b 01 19 27 02 08 07 28 06 01 02 03 04 05 06 35 01 01"
)
REAL_SET_APP_CONFIG_RX = bytes.fromhex("41 03 00 02 00 00 61 02 00 06 01 00 00 00 03 00")

REAL_RANGING_START_CONFIGURED_TX = bytes.fromhex("22 00 00 04 01 00 00 00")
REAL_RANGING_START_CONFIGURED_RX = bytes.fromhex(
    "42 00 00 01 00 60 01 00 01 02 61 02 00 06 01 00 00 00 02 00 62 00 00 38 00 "
    "00 00 00 01 00 00 00 00 c8 00 00 00 01 00 00 00 00 00 00 00 00 00 00 01 01 "
    "00 21 ff ff ff 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00 00 "
    "00 00 00 00 00 62 00 00 38 01 00 00 00 01 00 00 00 00 c8 00 00 00 01 00 00 "
    "00 00 00 00 00 00 00 00 01 01 00 21 ff ff ff 00 00 00 00 00 00 00 00 00 00 "
    "00 00 02 00 00 00 00 00 00 00 00 00 00 00 00"
)


def test_session_set_app_config_sends_expected_tvs_and_returns_ok() -> None:
    transport = FakeTransport(rx_data=REAL_SET_APP_CONFIG_RX)
    client = UciClient(transport)

    result = client.session_set_app_config(
        session_handle=1,
        device_type=DeviceType.CONTROLLER,
        device_role=DeviceRole.INITIATOR,
        device_mac_address=0x0000,
        dst_mac_addresses=[0x0001],
    )

    assert transport.tx_log == [REAL_SET_APP_CONFIG_TX]
    assert result.status == Status.OK
    assert result.rejected == ()


def test_ranging_start_on_configured_session_returns_ok_and_captures_ranging_data() -> None:
    transport = FakeTransport(rx_data=REAL_RANGING_START_CONFIGURED_RX)
    client = UciClient(transport)

    status = client.ranging_start(session_handle=1)

    assert transport.tx_log == [REAL_RANGING_START_CONFIGURED_TX]
    assert status == Status.OK

    ranging_data_notifications = [
        n for n in client.notifications if n.gid == 0x02 and n.oid == 0x00
    ]
    assert len(ranging_data_notifications) == 2


def test_poll_notifications_reads_without_sending_any_command() -> None:
    # SESSION_STATUS_NTF real disponible en el transporte sin que el cliente
    # haya enviado ningun comando: poll_notifications() debe leerla igual.
    notification_bytes = bytes.fromhex("61 02 00 06 01 00 00 00 00 00")
    transport = FakeTransport(rx_data=notification_bytes)
    client = UciClient(transport)

    result = client.poll_notifications(duration_s=0.05)

    assert transport.tx_log == []
    assert len(result) == 1
    assert result[0].gid == 0x01
    assert result[0].oid == 0x02
    assert result[0].payload == bytes.fromhex("01 00 00 00 00 00")
    assert client.notifications == result


def test_poll_notifications_returns_empty_list_when_nothing_arrives() -> None:
    transport = FakeTransport(rx_data=b"")
    client = UciClient(transport)

    result = client.poll_notifications(duration_s=0.05)

    assert result == []
    assert client.notifications == []
