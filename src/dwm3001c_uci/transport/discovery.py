"""Descubrimiento de puertos serie candidatos para la placa DWM3001CDK.

No hay todavia un VID/PID USB confirmado oficialmente para el puerto CDC ACM
del firmware ``*-UCI-FreeRTOS.hex`` (ver ``docs/protocolo-uci.md`` Seccion 5,
``[Sin confirmar]``). ``KNOWN_CANDIDATE_VID_PID`` es una lista heuristica, no
una fuente de verdad: confirmarla contra hardware real antes de depender de
ella para un descubrimiento automatico sin intervencion del usuario.
"""

from __future__ import annotations

from dataclasses import dataclass

from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

KNOWN_CANDIDATE_VID_PID: frozenset[tuple[int, int]] = frozenset(
    {
        (0x1915, 0x520F),  # Observado en un banco de pruebas real; sin confirmar oficialmente.
    }
)


@dataclass(frozen=True)
class PortCandidate:
    """Informacion resumida de un puerto serie candidato."""

    device: str
    description: str
    vid: int | None
    pid: int | None

    @property
    def is_known_candidate(self) -> bool:
        return (
            self.vid is not None
            and self.pid is not None
            and (self.vid, self.pid) in KNOWN_CANDIDATE_VID_PID
        )


def _to_candidate(info: ListPortInfo) -> PortCandidate:
    return PortCandidate(
        device=info.device,
        description=info.description or "",
        vid=info.vid,
        pid=info.pid,
    )


def list_all_ports() -> list[PortCandidate]:
    """Devuelve todos los puertos serie visibles en el sistema."""
    return [_to_candidate(info) for info in list_ports.comports()]


def list_known_candidates() -> list[PortCandidate]:
    """Filtra ``list_all_ports`` a los que matchean ``KNOWN_CANDIDATE_VID_PID``.

    Util como sugerencia por defecto en la CLI, nunca como unica opcion: el
    usuario debe poder elegir manualmente cualquier puerto de ``list_all_ports``.
    """
    return [port for port in list_all_ports() if port.is_known_candidate]
