"""Tests de core/models.py.

El payload de ejemplo es una captura real contra una placa DWM3001CDK con
firmware UCI (CORE_GET_DEVICE_INFO, GID=0x00 OID=0x02), no un valor sintetico.
"""

import pytest

from dwm3001c_uci.core.errors import UciPayloadError
from dwm3001c_uci.core.models import VersionTriplet, parse_device_info
from dwm3001c_uci.uci.enums import Status

REAL_DEVICE_INFO_PAYLOAD = bytes.fromhex(
    "00 02 00 02 00 02 00 01 10 34 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 50 56 34 58 32 30 0e e0 ca 09 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 00 00 00 00 00 02 03 ca de 00"
)


def test_parse_device_info_from_real_capture() -> None:
    info = parse_device_info(REAL_DEVICE_INFO_PAYLOAD)

    assert info.status == Status.OK
    assert info.uci_version == VersionTriplet(2, 0, 0)
    assert info.mac_version == VersionTriplet(2, 0, 0)
    assert info.phy_version == VersionTriplet(2, 0, 0)
    assert info.uci_test_version == VersionTriplet(1, 1, 0)
    assert len(info.vendor_data) == len(REAL_DEVICE_INFO_PAYLOAD) - 9


def test_version_triplet_str() -> None:
    assert str(VersionTriplet(2, 0, 0)) == "2.0.0"


def test_parse_device_info_raises_on_short_payload() -> None:
    with pytest.raises(UciPayloadError):
        parse_device_info(bytes([0x00, 0x02]))
