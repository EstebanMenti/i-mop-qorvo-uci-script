"""Tests de core/client.py (UciClient).

Los bytes de TX/RX usados como fixture son una captura real contra una placa
DWM3001CDK con firmware UCI (release QM33SDK-1.1.1, ver docs/protocolo-uci.md),
no valores sinteticos inventados.
"""

import pytest

from dwm3001c_uci.core.client import UciClient
from dwm3001c_uci.core.errors import UciTimeoutError
from dwm3001c_uci.uci.enums import Status
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
