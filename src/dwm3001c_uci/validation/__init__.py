"""Suite de validacion declarativa de comandos UCI (spec + runner + reporte)."""

from dwm3001c_uci.validation.report import render_text, to_dict
from dwm3001c_uci.validation.runner import CheckOutcome, run_checks
from dwm3001c_uci.validation.spec import DEFAULT_SPECS, CommandSpec

__all__ = [
    "DEFAULT_SPECS",
    "CheckOutcome",
    "CommandSpec",
    "render_text",
    "run_checks",
    "to_dict",
]
