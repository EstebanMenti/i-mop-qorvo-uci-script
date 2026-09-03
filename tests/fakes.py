"""Transporte falso para testear capas superiores sin hardware.

Ver docs/arquitectura.md Seccion 4 y docs/plan-implementacion.md fase F1.
"""

from __future__ import annotations

from collections import deque


class FakeTransport:
    """Cumple la interfaz :class:`dwm3001c_uci.transport.Transport`.

    ``rx_data`` es lo que el "firmware" le devuelve al cliente ya disponible
    desde el inicio (util para un solo intercambio comando/respuesta).

    ``responses`` simula una secuencia de varios intercambios reales: cada
    elemento se libera recien despues del `write()` que le corresponde (uno
    por llamada), en vez de estar todo disponible de entrada. Es necesario
    para encadenar varias capturas reales de hardware en un mismo test (p. ej.
    la suite de validacion, fase F6) sin que un `read()` temprano devuelva
    bytes de un intercambio que el cliente todavia no inicio.
    """

    def __init__(self, rx_data: bytes = b"", responses: list[bytes] | None = None) -> None:
        self._rx_buffer = bytearray(rx_data)
        self._pending_responses: deque[bytes] = deque(responses or [])
        self.tx_log: list[bytes] = []

    def queue_rx(self, data: bytes) -> None:
        """Encola bytes adicionales para que una lectura posterior los devuelva."""
        self._rx_buffer.extend(data)

    def read(self, size: int) -> bytes:
        chunk = bytes(self._rx_buffer[:size])
        del self._rx_buffer[:size]
        return chunk

    def write(self, data: bytes) -> int:
        self.tx_log.append(bytes(data))
        if self._pending_responses:
            self._rx_buffer.extend(self._pending_responses.popleft())
        return len(data)
