"""Ejecuta una lista de :class:`CommandSpec` contra un `UciClient` ya construido.

No abre el puerto ni conoce el transporte concreto (ver docs/arquitectura.md
Seccion 3.4): recibe el cliente ya listo, sea contra hardware real o contra un
`FakeTransport` en los tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from dwm3001c_uci.core.client import UciClient
from dwm3001c_uci.validation.spec import CommandSpec, Context


@dataclass(frozen=True)
class CheckOutcome:
    """Resultado de ejecutar y validar un :class:`CommandSpec`."""

    name: str
    description: str
    expected_description: str
    passed: bool
    result_repr: str
    error: str | None


def run_checks(client: UciClient, specs: Sequence[CommandSpec]) -> list[CheckOutcome]:
    """Ejecuta cada spec en orden, compartiendo un `context` entre todas.

    Un error en `run()` o `validate()` de un spec (incluida una `KeyError` en
    `context` por un paso anterior que no llego a completarse) se registra
    como check fallido en vez de interrumpir el resto de la corrida.
    """
    context: Context = {}
    outcomes: list[CheckOutcome] = []

    for spec in specs:
        try:
            result: Any = spec.run(client, context)
        except Exception as exc:  # noqa: BLE001 - un fallo de comando es un resultado a reportar, no un crash
            outcomes.append(
                _failed_outcome(spec, result_repr="", error=f"{type(exc).__name__}: {exc}")
            )
            continue

        try:
            passed = spec.validate(result, context)
        except Exception as exc:  # noqa: BLE001 - idem, sobre la validacion del resultado
            outcomes.append(
                _failed_outcome(
                    spec,
                    result_repr=repr(result),
                    error=f"error en validate(): {type(exc).__name__}: {exc}",
                )
            )
            continue

        outcomes.append(
            CheckOutcome(
                name=spec.name,
                description=spec.description,
                expected_description=spec.expected_description,
                passed=passed,
                result_repr=repr(result),
                error=None,
            )
        )

    return outcomes


def _failed_outcome(spec: CommandSpec, *, result_repr: str, error: str) -> CheckOutcome:
    return CheckOutcome(
        name=spec.name,
        description=spec.description,
        expected_description=spec.expected_description,
        passed=False,
        result_repr=result_repr,
        error=error,
    )
