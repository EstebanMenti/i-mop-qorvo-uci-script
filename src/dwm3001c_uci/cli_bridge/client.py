"""Cliente de alto nivel del comando `qorvo` del puente BLE (nRF52840).

Ver `I-mop-nrf52840-fw/doc/00_BLE_Protocol_Specification.md` Seccion 7.6.
Precondicion documentada y confirmada contra hardware real: el Qorvo remoto
debe estar encendido (`power_on()`) antes de enviarle cualquier comando de
texto -- sin eso no hay ninguna respuesta posible. El bridge recomienda
~1 segundo de espera despues de encenderlo para que el modulo termine de
arrancar (`DEFAULT_POWER_ON_SETTLE_S`).
"""

from __future__ import annotations

import time

from dwm3001c_uci.cli_bridge.ble_transport import DEFAULT_COMMAND_TIMEOUT_S, ShellTransport
from dwm3001c_uci.cli_bridge.errors import CliBridgeError

DEFAULT_POWER_ON_SETTLE_S = 1.5


class CliBridgeClient:
    """Envia comandos de texto de la CLI del Qorvo remoto a traves del puente BLE."""

    def __init__(self, transport: ShellTransport) -> None:
        self._transport = transport

    def connect(self, name_or_address: str) -> str:
        """Escanea/conecta por nombre (substring, p. ej. `"UWB-Node-2"`) o direccion BLE."""
        return self._transport.connect(name_or_address)

    def disconnect(self) -> None:
        self._transport.disconnect()

    def power_on(
        self, *, duration: str | None = None, settle_s: float = DEFAULT_POWER_ON_SETTLE_S
    ) -> str:
        """Enciende el modulo Qorvo remoto (`qorvo on`) y espera a que arranque."""
        command = "qorvo on" if duration is None else f"qorvo on -t {duration}"
        response = self._transport.send_line(command)
        if settle_s > 0:
            time.sleep(settle_s)
        return response

    def power_off(self, *, duration: str | None = None) -> str:
        """Apaga el modulo Qorvo remoto (`qorvo off`)."""
        command = "qorvo off" if duration is None else f"qorvo off -t {duration}"
        return self._transport.send_line(command)

    def send_qorvo_command(self, text: str, timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S) -> str:
        """Reenvia `text` a la CLI del Qorvo remoto (`qorvo <text>`), texto crudo sin tokenizar.

        Lanza `CliBridgeError` si el bridge respondio uno de sus mensajes de
        error conocidos (timeout hacia el Qorvo, puente UART no disponible,
        etc. -- ver especificacion del bridge Seccion 7.6), en vez de
        devolver ese texto como si fuera una respuesta valida de la CLI.
        """
        response = self._transport.send_line(f"qorvo {text}", timeout_s=timeout_s)
        if response.startswith("Error"):
            raise CliBridgeError(response)
        return response

    def stat(self) -> str:
        """`STAT`: estado y version del Qorvo remoto (JSON)."""
        return self.send_qorvo_command("STAT")

    def stop(self) -> str:
        """`STOP`: detiene la aplicacion FiRa activa (INITF/RESPF/LISTENER). Tarda ~0.3s."""
        return self.send_qorvo_command("STOP")

    def respf(self, **options: str | int) -> str:
        """`RESPF`: arranca el Qorvo remoto como responder FiRa TWR.

        `options` son los mismos nombres que documenta la ayuda de `RESPF` en
        el Qorvo (`CHAN`, `PCODE`, `RRU`, `ADDR`, `PADDR`, ...), pasados como
        `-NOMBRE=valor`. Requiere `MODE:NONE` (ver `stop()`).
        """
        return self.send_qorvo_command(_build_fira_command("RESPF", options))

    def initf(self, **options: str | int) -> str:
        """`INITF`: arranca el Qorvo remoto como initiator FiRa TWR. Ver `respf()`."""
        return self.send_qorvo_command(_build_fira_command("INITF", options))


def _build_fira_command(name: str, options: dict[str, str | int]) -> str:
    parts = [name]
    for key, value in options.items():
        parts.append(f"-{key.upper()}={value}")
    return " ".join(parts)
