"""Modelos de datos de respuestas/notificaciones UCI ya decodificadas.

Layout de CORE_GET_DEVICE_INFO_RSP confirmado por lectura directa de
`SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/fira_msg.py` (clase
`DeviceInfo_fira.decode_fira`, release `QM33SDK-1.1.1`), y verificado contra
una captura real de hardware (ver docs/protocolo-uci.md). Los bytes que siguen
a `uci_test_version` son extensiones especificas de Qorvo, fuera de alcance de
este proyecto (docs/protocolo-uci.md Seccion 6): se exponen sin decodificar en
`vendor_data`.
"""

from __future__ import annotations

from dataclasses import dataclass

from dwm3001c_uci.core.errors import UciPayloadError
from dwm3001c_uci.uci.enums import RangingMeasType, SessionState, Status

MIN_DEVICE_INFO_PAYLOAD_SIZE = 9
SESSION_INIT_RESPONSE_SIZE = 5
SESSION_STATUS_NOTIFICATION_SIZE = 6
RANGING_DATA_NOTIFICATION_HEADER_SIZE = 25


@dataclass(frozen=True)
class VersionTriplet:
    """Version de 3 numeros tal como la codifica UCI (1 byte major, 1 nibble c/u)."""

    major: int
    minor: int
    maintenance: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.maintenance}"


@dataclass(frozen=True)
class DeviceInfo:
    """Respuesta decodificada de `CORE_GET_DEVICE_INFO` (GID=0x00, OID=0x02)."""

    status: Status
    uci_version: VersionTriplet
    mac_version: VersionTriplet
    phy_version: VersionTriplet
    uci_test_version: VersionTriplet
    vendor_data: bytes


def parse_device_info(payload: bytes) -> DeviceInfo:
    """Decodifica el payload de una Response de `CORE_GET_DEVICE_INFO`."""
    if len(payload) < MIN_DEVICE_INFO_PAYLOAD_SIZE:
        raise UciPayloadError(
            f"payload de GET_DEVICE_INFO de {len(payload)} bytes, "
            f"se esperaban al menos {MIN_DEVICE_INFO_PAYLOAD_SIZE}"
        )

    def version_at(major_index: int) -> VersionTriplet:
        major = payload[major_index]
        minor_maintenance = payload[major_index + 1]
        return VersionTriplet(major, minor_maintenance >> 4, minor_maintenance & 0x0F)

    return DeviceInfo(
        status=Status(payload[0]),
        uci_version=version_at(1),
        mac_version=version_at(3),
        phy_version=version_at(5),
        uci_test_version=version_at(7),
        vendor_data=bytes(payload[MIN_DEVICE_INFO_PAYLOAD_SIZE:]),
    )


@dataclass(frozen=True)
class SessionInitResult:
    """Respuesta decodificada de `SESSION_INIT` (GID=0x01, OID=0x00).

    Layout confirmado contra `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/fira_msg.py`
    (clase `SessionData.decode_fira`, release `QM33SDK-1.1.1`).
    """

    status: Status
    session_handle: int


def parse_session_init_result(payload: bytes) -> SessionInitResult:
    """Decodifica el payload de una Response de `SESSION_INIT`."""
    if len(payload) < SESSION_INIT_RESPONSE_SIZE:
        raise UciPayloadError(
            f"payload de SESSION_INIT de {len(payload)} bytes, "
            f"se esperaban al menos {SESSION_INIT_RESPONSE_SIZE}"
        )
    return SessionInitResult(
        status=Status(payload[0]),
        session_handle=int.from_bytes(payload[1:5], "little"),
    )


@dataclass(frozen=True)
class SessionStatusNotification:
    """`SESSION_STATUS_NTF` decodificada (GID=0x01, OID=0x02).

    Layout confirmado contra `fira_msg.py` (clase `SessionStatus`, mismo release).
    `reason_code` se deja como entero crudo (no como `SessionStateChangeReason`)
    porque `uci/enums.py` solo transcribe los motivos genericos (`0x00`-`0x05`):
    el firmware puede legitimamente enviar codigos de error mas especificos que
    ese enum todavia no cubre, y un `ValueError` al decodificar una notificacion
    real seria peor que mostrar el valor crudo. Usar
    `session_state_change_reason_name(reason_code)` para el nombre simbolico.
    """

    session_id: int
    state: SessionState
    reason_code: int


def parse_session_status_notification(payload: bytes) -> SessionStatusNotification:
    """Decodifica el payload de una notificacion `SESSION_STATUS_NTF`."""
    if len(payload) < SESSION_STATUS_NOTIFICATION_SIZE:
        raise UciPayloadError(
            f"payload de SESSION_STATUS_NTF de {len(payload)} bytes, "
            f"se esperaban al menos {SESSION_STATUS_NOTIFICATION_SIZE}"
        )
    return SessionStatusNotification(
        session_id=int.from_bytes(payload[0:4], "little"),
        state=SessionState(payload[4]),
        reason_code=payload[5],
    )


@dataclass(frozen=True)
class RejectedAppConfigParam:
    """Un parametro de `SESSION_SET_APP_CONFIG` que el firmware rechazo, con su motivo."""

    param: int
    status: Status


@dataclass(frozen=True)
class AppConfigResult:
    """Resultado decodificado de una Response de `SESSION_SET_APP_CONFIG`.

    Formato confirmado contra `fira.py` del SDK (funcion `session_set_app_config`)
    -- **no es fijo**: si `status == Status.OK` la Response no trae nada mas;
    si no, trae la cantidad de parametros rechazados y, por cada uno, su tag y
    el `Status` especifico de ese parametro.
    """

    status: Status
    rejected: tuple[RejectedAppConfigParam, ...]


def parse_app_config_response(payload: bytes) -> AppConfigResult:
    """Decodifica el payload de una Response de `SESSION_SET_APP_CONFIG`."""
    if not payload:
        raise UciPayloadError("payload de SESSION_SET_APP_CONFIG vacio")

    status = Status(payload[0])
    if status == Status.OK:
        return AppConfigResult(status=status, rejected=())

    if len(payload) < 2:
        raise UciPayloadError(
            "payload de SESSION_SET_APP_CONFIG con Status de error "
            "pero sin la cantidad de parametros rechazados"
        )

    count = payload[1]
    expected_size = 2 + count * 2
    if len(payload) < expected_size:
        raise UciPayloadError(
            f"payload de SESSION_SET_APP_CONFIG de {len(payload)} bytes, "
            f"se esperaban {expected_size} para {count} parametros rechazados"
        )

    rejected = tuple(
        RejectedAppConfigParam(param=payload[2 + 2 * i], status=Status(payload[3 + 2 * i]))
        for i in range(count)
    )
    return AppConfigResult(status=status, rejected=rejected)


@dataclass(frozen=True)
class RangingDataNotification:
    """Header de `RANGING_DATA_NTF` (GID=0x02, OID=0x00, `MT=NOTIFICATION`).

    Layout confirmado contra `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/qorvo_msg.py`
    (clase `RangingData.__init__`, release `QM33SDK-1.1.1`) y verificado
    contra una captura real de hardware (ver docs/protocolo-uci.md): un solo
    dispositivo sin par ya genera esta notificacion en cada ronda de ranging,
    con `n_measurements=1` aunque no haya respuesta de otro dispositivo.

    Las mediciones individuales (`n_measurements` registros al final del
    payload, con un formato que depende de `measurement_type` -- TWR, OWR AoA,
    etc.) **no se decodifican todavia**: quedan crudas en `measurements_raw`.
    """

    sequence_number: int
    session_handle: int
    ranging_interval_ms: int
    measurement_type: RangingMeasType
    mac_address_size_bytes: int
    primary_session_id: int
    n_measurements: int
    measurements_raw: bytes


def parse_ranging_data_notification(payload: bytes) -> RangingDataNotification:
    """Decodifica el header de una notificacion `RANGING_DATA_NTF` (sin las mediciones)."""
    if len(payload) < RANGING_DATA_NOTIFICATION_HEADER_SIZE:
        raise UciPayloadError(
            f"payload de RANGING_DATA_NTF de {len(payload)} bytes, "
            f"se esperaban al menos {RANGING_DATA_NOTIFICATION_HEADER_SIZE} para el header"
        )
    return RangingDataNotification(
        sequence_number=int.from_bytes(payload[0:4], "little"),
        session_handle=int.from_bytes(payload[4:8], "little"),
        # payload[8]: RFU
        ranging_interval_ms=int.from_bytes(payload[9:13], "little"),
        measurement_type=RangingMeasType(payload[13]),
        # payload[14]: RFU
        mac_address_size_bytes=2 if payload[15] == 0 else 8,
        primary_session_id=int.from_bytes(payload[16:20], "little"),
        # payload[20:24]: RFU
        n_measurements=payload[24],
        measurements_raw=bytes(payload[RANGING_DATA_NOTIFICATION_HEADER_SIZE:]),
    )
