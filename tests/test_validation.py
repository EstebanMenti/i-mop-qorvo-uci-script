"""Tests de validation/spec.py, runner.py y report.py.

El test `test_run_checks_full_sequence_against_real_hardware_captures` encadena
TODAS las capturas reales de hardware ya usadas en tests/test_core_client.py,
en el mismo orden en que se ejecutaron contra la placa real, para probar
`DEFAULT_SPECS` de punta a punta sin necesidad de hardware conectado.
"""

from dwm3001c_uci.core.client import UciClient
from dwm3001c_uci.validation.report import render_text, to_dict
from dwm3001c_uci.validation.runner import CheckOutcome, run_checks
from dwm3001c_uci.validation.spec import DEFAULT_SPECS, CommandSpec
from tests.fakes import FakeTransport
from tests.test_core_client import (
    REAL_GET_CAPS_RX,
    REAL_GET_DEVICE_INFO_RX,
    REAL_RANGING_GET_COUNT_RX,
    REAL_RANGING_START_RX,
    REAL_RANGING_STOP_RX,
    REAL_RESET_RX,
    REAL_SESSION_DEINIT_RX,
    REAL_SESSION_GET_COUNT_ACTIVE_RX,
    REAL_SESSION_GET_COUNT_EMPTY_RX,
    REAL_SESSION_GET_STATE_RX,
    REAL_SESSION_INIT_RX,
)


def test_run_checks_full_sequence_against_real_hardware_captures() -> None:
    # Mismo orden que DEFAULT_SPECS: reset, device_info, caps, session_init,
    # get_state, get_count(activa), ranging get_count, ranging start, ranging
    # stop, session_deinit, get_count(vacia).
    responses = [
        REAL_RESET_RX,
        REAL_GET_DEVICE_INFO_RX,
        REAL_GET_CAPS_RX,
        REAL_SESSION_INIT_RX,
        REAL_SESSION_GET_STATE_RX,
        REAL_SESSION_GET_COUNT_ACTIVE_RX,
        REAL_RANGING_GET_COUNT_RX,
        REAL_RANGING_START_RX,
        REAL_RANGING_STOP_RX,
        REAL_SESSION_DEINIT_RX,
        REAL_SESSION_GET_COUNT_EMPTY_RX,
    ]
    transport = FakeTransport(responses=responses)
    client = UciClient(transport)

    outcomes = run_checks(client, DEFAULT_SPECS)

    assert len(outcomes) == len(DEFAULT_SPECS)
    failed = [o for o in outcomes if not o.passed]
    assert failed == [], f"checks fallidos: {[(o.name, o.error) for o in failed]}"
    assert all(o.error is None for o in outcomes)


def test_run_checks_marks_failure_when_run_raises() -> None:
    def _raise(client: UciClient, context: dict) -> None:
        raise RuntimeError("fallo simulado")

    spec = CommandSpec(
        name="FALLA_EN_RUN",
        description="spec de prueba que siempre falla al ejecutar",
        run=_raise,
        validate=lambda result, context: True,
        expected_description="no deberia llegar a validar",
    )
    client = UciClient(FakeTransport())

    outcomes = run_checks(client, [spec])

    assert len(outcomes) == 1
    assert outcomes[0].passed is False
    assert outcomes[0].error is not None
    assert "RuntimeError" in outcomes[0].error


def test_run_checks_marks_failure_when_validate_returns_false() -> None:
    spec = CommandSpec(
        name="RESET_INESPERADO",
        description="espera un status que el reset real no da",
        run=lambda client, context: client.reset(),
        validate=lambda result, context: False,
        expected_description="algo que nunca pasa",
    )
    transport = FakeTransport(rx_data=REAL_RESET_RX)
    client = UciClient(transport)

    outcomes = run_checks(client, [spec])

    assert outcomes[0].passed is False
    assert outcomes[0].error is None  # el comando corrio bien, solo no cumplio la asercion


def test_run_checks_continues_after_a_dependent_step_fails() -> None:
    # Si SESSION_INIT nunca corre (spec vacia), el siguiente paso que depende
    # de context["session_handle"] debe fallar con KeyError capturada, no
    # interrumpir la corrida completa.
    spec_missing_handle = CommandSpec(
        name="GET_STATE_SIN_HANDLE",
        description="usa un context vacio a proposito",
        run=lambda client, context: client.get_session_state(context["session_handle"]),
        validate=lambda result, context: True,
        expected_description="no aplica",
    )
    other_spec = CommandSpec(
        name="RESET_OK",
        description="corre normalmente despues del fallo anterior",
        run=lambda client, context: client.reset(),
        validate=lambda result, context: result == result,
        expected_description="Status.OK",
    )
    transport = FakeTransport(rx_data=REAL_RESET_RX)
    client = UciClient(transport)

    outcomes = run_checks(client, [spec_missing_handle, other_spec])

    assert outcomes[0].passed is False
    assert "KeyError" in (outcomes[0].error or "")
    assert outcomes[1].passed is True


def test_render_text_reports_pass_and_fail_counts() -> None:
    outcomes = [
        CheckOutcome("A", "desc A", "esperado A", True, "ok", None),
        CheckOutcome("B", "desc B", "esperado B", False, "algo", "boom"),
    ]

    text = render_text(outcomes, title="Reporte de prueba")

    assert "Reporte de prueba" in text
    assert "1/2 checks OK" in text
    assert "[OK  ] A" in text
    assert "[FAIL] B" in text
    assert "boom" in text


def test_render_text_includes_metadata_when_given() -> None:
    outcomes = [CheckOutcome("A", "desc", "esperado", True, "ok", None)]

    text = render_text(outcomes, metadata={"firmware": "QM33SDK-1.1.1", "puerto": "COM29"})

    assert "firmware: QM33SDK-1.1.1" in text
    assert "puerto: COM29" in text


def test_to_dict_serializes_outcomes() -> None:
    outcomes = [CheckOutcome("A", "desc", "esperado", True, "ok", None)]

    data = to_dict(outcomes)

    assert data == [
        {
            "name": "A",
            "description": "desc",
            "expected": "esperado",
            "passed": True,
            "result": "ok",
            "error": None,
        }
    ]
