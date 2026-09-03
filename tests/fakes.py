"""Transporte falso para testear capas superiores sin hardware.

Ver docs/arquitectura.md Seccion 4 y docs/plan-implementacion.md fase F1.
"""

from __future__ import annotations


class FakeTransport:
    """Cumple la interfaz :class:`dwm3001c_uci.transport.Transport`.

    ``rx_data`` es lo que el "firmware" le devuelve al cliente en las
    sucesivas llamadas a :meth:`read`. Cada ``write`` queda registrado en
    ``tx_log`` para poder asertar que se envio la trama esperada.
    """

    def __init__(self, rx_data: bytes = b"") -> None:
        self._rx_buffer = bytearray(rx_data)
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
        return len(data)
