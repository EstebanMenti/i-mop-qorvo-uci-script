"""Enums del protocolo UCI, segun docs/protocolo-uci.md (Secciones 1, 2 y 4).

Los valores fueron relevados y confirmados contra la implementacion Python de
referencia de Qorvo (SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/*.py, release
QM33SDK-1.1.1) -- ver la nota legal en docs/protocolo-uci.md Seccion 7 sobre
por que este modulo se reimplementa de forma independiente en vez de copiar
ese codigo fuente.
"""

from __future__ import annotations

from enum import IntEnum


class MessageType(IntEnum):
    """Campo MT (3 bits) del byte 0 de una trama UCI."""

    DATA_PACKET = 0
    COMMAND = 1
    RESPONSE = 2
    NOTIFICATION = 3


class Gid(IntEnum):
    """Group ID (4 bits) del byte 0 de una trama UCI."""

    CORE = 0x00
    SESSION = 0x01
    RANGING = 0x02
    TEST = 0x0D


class OidCore(IntEnum):
    """Opcodes del grupo Core (Gid.CORE)."""

    RESET = 0x00
    DEVICE_STATUS_NTF = 0x01
    GET_DEVICE_INFO = 0x02
    GET_CAPS = 0x03
    SET_CONFIG = 0x04
    GET_CONFIG = 0x05
    GENERIC_ERROR_NTF = 0x07
    GET_TIME = 0x08


class OidSession(IntEnum):
    """Opcodes del grupo Session (Gid.SESSION)."""

    INIT = 0x00
    DEINIT = 0x01
    STATUS_NTF = 0x02
    SET_APP_CONFIG = 0x03
    GET_APP_CONFIG = 0x04
    GET_COUNT = 0x05
    GET_STATE = 0x06
    UPDATE_MULTICAST_LIST = 0x07
    SET_ANCHOR_RANGING_ROUNDS = 0x08
    SET_TAG_ACTIVITY = 0x09
    GET_DATA_SIZE = 0x0B
    UPDATE_HUS = 0x0C


class OidRanging(IntEnum):
    """Opcodes del grupo Ranging (Gid.RANGING)."""

    START = 0x00
    STOP = 0x01
    GET_COUNT = 0x03
    DATA_CREDIT = 0x04
    DATA_TRANSFER_STATUS = 0x05


class OidTest(IntEnum):
    """Opcodes del grupo Test (Gid.TEST)."""

    CONFIG_SET = 0x00
    CONFIG_GET = 0x01
    PERIODIC_TX = 0x02
    PER_RX = 0x03
    RX = 0x05
    LOOPBACK = 0x06
    STOP_SESSION = 0x07
    SS_TWR = 0x08


class Status(IntEnum):
    """Codigos de estado UCI (docs/protocolo-uci.md Seccion 4).

    Rango propietario 0x50-0xFF: solo se enumeran aqui los confirmados contra
    la fuente; el resto de ese rango es especifico de Qorvo y esta fuera del
    alcance de docs/protocolo-uci.md Seccion 6.
    """

    OK = 0x00
    REJECTED = 0x01
    FAILED = 0x02
    SYNTAX_ERROR = 0x03
    INVALID_PARAM = 0x04
    INVALID_RANGE = 0x05
    INVALID_MESSAGE_SIZE = 0x06
    UNKNOWN_GID = 0x07
    UNKNOWN_OID = 0x08
    READ_ONLY = 0x09
    COMMAND_RETRY = 0x0A
    # RFU 0x0B-0x0F

    ERROR_SESSION_NOT_EXIST = 0x11
    ERROR_SESSION_DUPLICATE = 0x12
    ERROR_SESSION_ACTIVE = 0x13
    ERROR_MAX_SESSIONS_EXCEEDED = 0x14
    ERROR_SESSION_NOT_CONFIGURED = 0x15
    ERROR_ACTIVE_SESSIONS_ONGOING = 0x16
    ERROR_MULTICAST_LIST_FULL = 0x17
    # RFU 0x18-0x19
    ERROR_UWB_INITIALIZATION_TIME_TOO_OLD = 0x1A
    RANGING_NEGATIVE_DISTANCE = 0x1B

    RANGING_TX_FAILED = 0x20
    RANGING_RX_TIMEOUT = 0x21
    RANGING_RX_PHY_DEC_FAILED = 0x22
    RANGING_RX_PHY_TOA_FAILED = 0x23
    RANGING_RX_PHY_STS_FAILED = 0x24
    RANGING_RX_MAC_DEC_FAILED = 0x25
    RANGING_RX_MAC_IE_DEC_FAILED = 0x26
    RANGING_RX_MAC_IE_MISSING = 0x27
    ERROR_ROUND_INDEX_NOT_ACTIVATED = 0x28
    ERROR_NUMBER_OF_ACTIVE_ROUND_EXCEEDED = 0x29
    ERROR_DL_TDOA_DEVICE_ADDRESS_NOT_MATCHING_IN_REPLY_TIME_LIST = 0x2A
    # RFU 0x2B-0x4F

    # Codigos propietarios (0x50-0xFF), confirmados contra la fuente:
    ERROR_SE_BUSY = 0x50
    ERROR_CCC_LIFE_CYCLE = 0x51
    UNKNOWN = 0xFF


def status_name(value: int) -> str:
    """Nombre simbolico de un codigo de status, con fallback seguro.

    El firmware puede devolver, en el futuro, un codigo de status que este
    modulo todavia no enumera (p. ej. dentro del rango propietario 0x50-0xFF).
    No fallar en ese caso: reportar el valor crudo en vez de lanzar una
    excepcion al decodificar una respuesta.
    """
    try:
        return Status(value).name
    except ValueError:
        return f"UNKNOWN_STATUS(0x{value:02X})"
