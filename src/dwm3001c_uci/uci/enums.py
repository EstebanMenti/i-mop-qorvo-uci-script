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


class SessionType(IntEnum):
    """Tipo de sesion, parametro de `SESSION_INIT` (confirmado contra `fira_enums.py`)."""

    RANGING = 0x00
    RANGING_AND_DATA = 0x01
    DATA = 0x02
    RANGING_PHASE = 0x03
    DATA_PHASE = 0x04
    RANGING_AND_DATA_PHASE = 0x05
    HUS_PRIMARY_SESSION = 0x9F
    DEVICE_TEST_MODE = 0xD0


class SessionState(IntEnum):
    """Estado de una sesion, payload de `SESSION_STATUS_NTF` y de `SESSION_GET_STATE`."""

    INIT = 0x00
    DEINIT = 0x01
    ACTIVE = 0x02
    IDLE = 0x03


class SessionStateChangeReason(IntEnum):
    """Motivo de un cambio de estado de sesion, segundo campo de `SESSION_STATUS_NTF`.

    Confirmado contra `fira_enums.py`. Solo se listan los valores genericos
    (`0x00`-`0x05`); el resto del rango documentado en esa fuente (errores de
    configuracion muy especificos de FiRa 2.0) no esta transcripto aqui para no
    duplicar una tabla larga que este proyecto todavia no necesita — agregar
    valores puntuales aqui a medida que se observen en las notificaciones
    reales de la placa, citando la fuente.
    """

    STATE_CHANGE_WITH_SESSION_MANAGEMENT_COMMANDS = 0x00
    MAX_RANGING_ROUND_RETRY_COUNT_REACHED = 0x01
    MAX_NUMBER_OF_MEASUREMENT_REACHED = 0x02
    SESSION_SUSPENDED_DUE_TO_INBAND_SIGNAL = 0x03
    SESSION_RESUMED_DUE_TO_INBAND_SIGNAL = 0x04
    SESSION_STOPPED_DUE_TO_INBAND_SIGNAL = 0x05


def session_state_change_reason_name(value: int) -> str:
    """Nombre simbolico de un motivo de cambio de estado, con fallback seguro."""
    try:
        return SessionStateChangeReason(value).name
    except ValueError:
        return f"UNKNOWN_REASON(0x{value:02X})"


class DeviceState(IntEnum):
    """Estado del dispositivo, payload de `CORE_DEVICE_STATUS_NTF` (confirmado)."""

    READY = 0x01
    ACTIVE = 0x02
    ERROR = 0xFF


def device_state_name(value: int) -> str:
    """Nombre simbolico de un estado de dispositivo, con fallback seguro."""
    try:
        return DeviceState(value).name
    except ValueError:
        return f"UNKNOWN_DEVICE_STATE(0x{value:02X})"


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
