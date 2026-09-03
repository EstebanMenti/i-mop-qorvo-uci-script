"""Genera el reporte de una corrida de validacion a partir de sus `CheckOutcome`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from dwm3001c_uci.validation.runner import CheckOutcome


def render_text(
    outcomes: Sequence[CheckOutcome],
    *,
    title: str = "Reporte de validacion UCI",
    metadata: dict[str, str] | None = None,
) -> str:
    """Reporte legible en texto plano, con resumen y detalle por check."""
    passed_count = sum(1 for outcome in outcomes if outcome.passed)
    lines = [title, "=" * len(title), ""]

    if metadata:
        for key, value in metadata.items():
            lines.append(f"{key}: {value}")
        lines.append("")

    lines.append(f"Resultado: {passed_count}/{len(outcomes)} checks OK")
    lines.append("")

    for outcome in outcomes:
        mark = "OK  " if outcome.passed else "FAIL"
        lines.append(f"[{mark}] {outcome.name} - {outcome.description}")
        lines.append(f"       esperado:  {outcome.expected_description}")
        lines.append(f"       obtenido:  {outcome.result_repr}")
        if outcome.error:
            lines.append(f"       error:     {outcome.error}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def to_dict(outcomes: Sequence[CheckOutcome]) -> list[dict[str, Any]]:
    """Representacion serializable (p. ej. a JSON) de los resultados, para archivar."""
    return [
        {
            "name": outcome.name,
            "description": outcome.description,
            "expected": outcome.expected_description,
            "passed": outcome.passed,
            "result": outcome.result_repr,
            "error": outcome.error,
        }
        for outcome in outcomes
    ]
