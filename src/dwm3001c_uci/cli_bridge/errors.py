"""Excepciones del puente CLI-sobre-BLE. No heredan de `UciError` (`core/errors.py`):
son un protocolo completamente distinto (shell de texto sobre BLE, no UCI).
"""

from __future__ import annotations


class BleShellError(Exception):
    """Error del transporte BLE/shell (conexion, escaneo, timeout de transporte)."""


class BleShellTimeoutError(BleShellError):
    """No llego el prompt del shell dentro del timeout configurado."""


class CliBridgeError(Exception):
    """El puente o el Qorvo remoto respondieron un error de texto reconocido.

    No hereda de `BleShellError`: la conexion BLE funciono bien, el error es
    del nivel de aplicacion (el bridge no pudo hablarle al Qorvo, o el Qorvo
    respondio `KO`).
    """
