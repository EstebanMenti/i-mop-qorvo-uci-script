"""Spec declarativa de la suite de validacion: que comandos ejecutar y que esperar.

Cada :class:`CommandSpec` combina una accion (`run`) que ejecuta un comando
sobre un `UciClient` y una aserción (`validate`) sobre el resultado. `context`
es un diccionario compartido entre specs de una misma corrida, para pasos que
dependen del resultado de uno anterior (p. ej. `session_handle`).

Cubre los grupos `Core` (F3), `Session` (F4) y `Ranging` (F5) ya implementados
(ver docs/plan-implementacion.md). No cubre `set_app_config`/`get_app_config`
ni un ciclo de ranging exitoso: no estan implementados todavia.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dwm3001c_uci.core.client import UciClient
from dwm3001c_uci.uci.enums import SessionState, SessionType, Status

Context = dict[str, Any]


@dataclass(frozen=True)
class CommandSpec:
    """Un comando a ejecutar y validar durante la suite."""

    name: str
    description: str
    run: Callable[[UciClient, Context], Any]
    validate: Callable[[Any, Context], bool]
    expected_description: str


def _run_core_reset(client: UciClient, context: Context) -> Status:
    return client.reset()


def _validate_status_ok(result: Any, context: Context) -> bool:
    return bool(result == Status.OK)


def _run_core_get_device_info(client: UciClient, context: Context) -> Any:
    return client.get_device_info()


def _validate_device_info_status_ok(result: Any, context: Context) -> bool:
    return bool(result.status == Status.OK)


def _run_core_get_caps(client: UciClient, context: Context) -> Any:
    return client.get_caps_raw()


def _validate_status_tuple_ok(result: Any, context: Context) -> bool:
    status, _ = result
    return bool(status == Status.OK)


def _run_session_init(client: UciClient, context: Context) -> Any:
    result = client.session_init(session_id=1, session_type=SessionType.RANGING)
    context["session_handle"] = result.session_handle
    return result


def _validate_session_init_ok(result: Any, context: Context) -> bool:
    return bool(result.status == Status.OK)


def _run_session_get_state(client: UciClient, context: Context) -> Any:
    return client.get_session_state(context["session_handle"])


def _validate_session_state_is_init(result: Any, context: Context) -> bool:
    status, state = result
    return bool(status == Status.OK and SessionState(state) == SessionState.INIT)


def _run_session_get_count_active(client: UciClient, context: Context) -> Any:
    return client.get_session_count()


def _validate_session_count_is_one(result: Any, context: Context) -> bool:
    status, count = result
    return bool(status == Status.OK and count == 1)


def _run_ranging_get_count(client: UciClient, context: Context) -> Any:
    return client.get_ranging_count(context["session_handle"])


def _validate_ranging_count_is_zero(result: Any, context: Context) -> bool:
    status, count = result
    return bool(status == Status.OK and count == 0)


def _run_ranging_start(client: UciClient, context: Context) -> Status:
    return client.ranging_start(context["session_handle"])


def _validate_ranging_start_not_configured(result: Any, context: Context) -> bool:
    # Sin SESSION_SET_APP_CONFIG (no implementado todavia, ver
    # docs/plan-implementacion.md F4), el resultado correcto y confirmado
    # contra hardware real es este error -- no Status.OK. Cuando se
    # implemente SET_APP_CONFIG, esta spec debe actualizarse para configurar
    # la sesion antes y esperar Status.OK.
    return bool(result == Status.ERROR_SESSION_NOT_CONFIGURED)


def _run_ranging_stop(client: UciClient, context: Context) -> Status:
    return client.ranging_stop(context["session_handle"])


def _run_session_deinit(client: UciClient, context: Context) -> Status:
    return client.session_deinit(context["session_handle"])


def _run_session_get_count_empty(client: UciClient, context: Context) -> Any:
    return client.get_session_count()


def _validate_session_count_is_zero(result: Any, context: Context) -> bool:
    status, count = result
    return bool(status == Status.OK and count == 0)


DEFAULT_SPECS: list[CommandSpec] = [
    CommandSpec(
        name="CORE_RESET",
        description="Reinicia el dispositivo (payload 0x00).",
        run=_run_core_reset,
        validate=_validate_status_ok,
        expected_description="Status.OK",
    ),
    CommandSpec(
        name="CORE_GET_DEVICE_INFO",
        description="Consulta version de UCI/MAC/PHY del dispositivo.",
        run=_run_core_get_device_info,
        validate=_validate_device_info_status_ok,
        expected_description="status OK",
    ),
    CommandSpec(
        name="CORE_GET_CAPS",
        description="Consulta la lista de capacidades (sin decodificar el TLV).",
        run=_run_core_get_caps,
        validate=_validate_status_tuple_ok,
        expected_description="status OK",
    ),
    CommandSpec(
        name="SESSION_INIT",
        description="Crea una sesion de tipo RANGING con session_id=1.",
        run=_run_session_init,
        validate=_validate_session_init_ok,
        expected_description="status OK",
    ),
    CommandSpec(
        name="SESSION_GET_STATE",
        description="Consulta el estado de la sesion recien creada.",
        run=_run_session_get_state,
        validate=_validate_session_state_is_init,
        expected_description="status OK, SessionState.INIT",
    ),
    CommandSpec(
        name="SESSION_GET_COUNT (activa)",
        description="Cuenta de sesiones con la sesion todavia activa.",
        run=_run_session_get_count_active,
        validate=_validate_session_count_is_one,
        expected_description="status OK, count=1",
    ),
    CommandSpec(
        name="RANGING_GET_COUNT",
        description="Cuenta de mediciones de ranging antes de iniciar.",
        run=_run_ranging_get_count,
        validate=_validate_ranging_count_is_zero,
        expected_description="status OK, count=0",
    ),
    CommandSpec(
        name="RANGING_START",
        description="Intenta iniciar ranging sobre una sesion sin configurar.",
        run=_run_ranging_start,
        validate=_validate_ranging_start_not_configured,
        expected_description="Status.ERROR_SESSION_NOT_CONFIGURED (sesion sin SET_APP_CONFIG)",
    ),
    CommandSpec(
        name="RANGING_STOP",
        description="Detiene el intento de ranging anterior.",
        run=_run_ranging_stop,
        validate=_validate_ranging_start_not_configured,
        expected_description="Status.ERROR_SESSION_NOT_CONFIGURED (coherente con RANGING_START)",
    ),
    CommandSpec(
        name="SESSION_DEINIT",
        description="Elimina la sesion creada al principio de la corrida.",
        run=_run_session_deinit,
        validate=_validate_status_ok,
        expected_description="Status.OK",
    ),
    CommandSpec(
        name="SESSION_GET_COUNT (vacia)",
        description="Cuenta de sesiones tras eliminar la sesion.",
        run=_run_session_get_count_empty,
        validate=_validate_session_count_is_zero,
        expected_description="status OK, count=0",
    ),
]
