"""Transporte serie sobre el puerto COM virtual (USB CDC ACM) de la placa DWM3001CDK.

Los parametros de puerto por defecto (``DEFAULT_BAUDRATE``) estan marcados como
``[Sin confirmar]`` en ``docs/protocolo-uci.md`` Seccion 5: no se debe asumir que
coinciden con los del firmware CLI de texto sin verificarlo contra hardware real
(ver ``docs/plan-implementacion.md`` fase F1).
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

import serial

DEFAULT_BAUDRATE = 115200
"""Valor provisorio, heredado del firmware CLI. [Sin confirmar] para firmware UCI."""

DEFAULT_TIMEOUT_S = 1.0


class Transport(Protocol):
    """Interfaz minima que necesitan las capas ``uci``/``core``.

    Cualquier implementacion (serie real, :class:`FakeTransport` en los tests)
    debe cumplir esta interfaz para ser intercambiable.
    """

    def read(self, size: int) -> bytes:
        """Lee hasta ``size`` bytes, bloqueando como maximo el timeout configurado."""
        ...

    def write(self, data: bytes) -> int:
        """Escribe ``data`` y devuelve la cantidad de bytes escritos."""
        ...


class SerialLink:
    """Transporte serie real sobre :mod:`pyserial`.

    No interpreta el contenido de los bytes: es responsabilidad de la capa
    ``uci`` (framing) y ``core`` (cliente) darles significado.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout_s = timeout_s
        self._serial: serial.Serial | None = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def open(self) -> None:
        if self.is_open:
            return
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self._timeout_s,
        )

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def read(self, size: int) -> bytes:
        if self._serial is None:
            raise RuntimeError("el puerto no esta abierto: llamar a open() primero")
        return self._serial.read(size)

    def write(self, data: bytes) -> int:
        if self._serial is None:
            raise RuntimeError("el puerto no esta abierto: llamar a open() primero")
        written = self._serial.write(data)
        if written is None:
            raise RuntimeError("la escritura al puerto serie no devolvio la cantidad de bytes")
        return written

    def __enter__(self) -> SerialLink:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
