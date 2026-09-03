"""Los valores deben coincidir exactamente con docs/protocolo-uci.md (Secciones 2 y 4),
confirmados contra SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/fira_enums.py.
"""

from dwm3001c_uci.uci.enums import (
    Gid,
    MessageType,
    OidCore,
    OidRanging,
    OidSession,
    OidTest,
    Status,
    status_name,
)


def test_message_type_values() -> None:
    assert MessageType.DATA_PACKET == 0
    assert MessageType.COMMAND == 1
    assert MessageType.RESPONSE == 2
    assert MessageType.NOTIFICATION == 3


def test_gid_values() -> None:
    assert Gid.CORE == 0x00
    assert Gid.SESSION == 0x01
    assert Gid.RANGING == 0x02
    assert Gid.TEST == 0x0D


def test_oid_core_values() -> None:
    assert OidCore.RESET == 0x00
    assert OidCore.DEVICE_STATUS_NTF == 0x01
    assert OidCore.GET_DEVICE_INFO == 0x02
    assert OidCore.GET_CAPS == 0x03
    assert OidCore.GET_TIME == 0x08


def test_oid_session_values() -> None:
    assert OidSession.INIT == 0x00
    assert OidSession.STATUS_NTF == 0x02
    assert OidSession.GET_DATA_SIZE == 0x0B
    assert OidSession.UPDATE_HUS == 0x0C


def test_oid_ranging_values() -> None:
    assert OidRanging.START == 0x00
    assert OidRanging.STOP == 0x01
    assert OidRanging.DATA_TRANSFER_STATUS == 0x05


def test_oid_test_values() -> None:
    assert OidTest.CONFIG_SET == 0x00
    assert OidTest.SS_TWR == 0x08


def test_status_values() -> None:
    assert Status.OK == 0x00
    assert Status.COMMAND_RETRY == 0x0A
    assert Status.ERROR_MULTICAST_LIST_FULL == 0x17
    assert Status.RANGING_RX_TIMEOUT == 0x21
    assert Status.ERROR_SE_BUSY == 0x50


def test_status_name_known_value() -> None:
    assert status_name(0x00) == "OK"
    assert status_name(0x17) == "ERROR_MULTICAST_LIST_FULL"


def test_status_name_unknown_value_does_not_raise() -> None:
    assert status_name(0x99) == "UNKNOWN_STATUS(0x99)"
