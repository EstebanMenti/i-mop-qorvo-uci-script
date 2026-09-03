"""Jerarquia de excepciones del cliente UCI de alto nivel."""

from __future__ import annotations

from dwm3001c_uci.uci.enums import Status


class UciError(Exception):
    """Error base de la capa `core`."""


class UciTimeoutError(UciError):
    """No se recibio la Response esperada dentro del timeout configurado."""


class UciPayloadError(UciError):
    """El payload de una Response/Notification no tiene el formato esperado."""


class UciStatusError(UciError):
    """Una Response llego con un `Status` distinto del esperado.

    No se lanza automaticamente desde `UciClient` (ver core/client.py): cada
    comando devuelve su `Status` y es responsabilidad de quien lo llama (p. ej.
    la suite de validacion) decidir si un status distinto de OK es un error.
    Queda disponible para esos casos de uso.
    """

    def __init__(self, status: Status, context: str) -> None:
        super().__init__(f"{context}: status={status.name} (0x{status.value:02X})")
        self.status = status
