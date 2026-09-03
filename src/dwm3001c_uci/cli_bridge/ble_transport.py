"""Transporte BLE para el shell de Zephyr sobre Nordic UART Service (NUS).

Protocolo confirmado contra `I-mop-nrf52840-fw/doc/00_BLE_Protocol_Specification.md`
(version 1.21, `qorvo` documentado como "IMPLEMENTADO Y VALIDADO EN HARDWARE
REAL"): shell de Zephyr expuesto sobre NUS (backend `shell_bt_nus`), sin eco
ni secuencias ANSI/VT100 (`CONFIG_SHELL_ECHO_STATUS=n`,
`CONFIG_SHELL_VT100_COMMANDS=n`), terminador de linea `\\n` (el `\\r` se
ignora), y el shell imprime su propio prompt (`bt_nus:~$ `) al final de cada
respuesta -- esa es la senal que usa este modulo para saber que una respuesta
termino, en vez de replicar la ventana de silencio de 400 ms que usa el
firmware del bridge internamente (ese detalle es interno al bridge, no hace
falta reproducirlo del lado del host).

Usa `bleak` (backend WinRT en Windows) con un hilo dedicado corriendo su
propio event loop de asyncio: es un requisito del backend WinRT que todas las
llamadas de una misma conexion GATT se hagan desde el mismo hilo/loop. Los
metodos publicos de `BleShellTransport` son sincronos.
"""

from __future__ import annotations

import asyncio
import re
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Protocol, cast

from bleak import BleakClient, BleakScanner

from dwm3001c_uci.cli_bridge.errors import BleShellError, BleShellTimeoutError


class ShellTransport(Protocol):
    """Interfaz minima que necesita `CliBridgeClient` (ver `core/transport.Transport`
    para el equivalente del lado UCI). Cualquier implementacion (`BleShellTransport`
    real, un doble de prueba) puede usarse en su lugar sin heredar de nada."""

    def connect(self, name_or_address: str) -> str: ...

    def disconnect(self) -> None: ...

    def send_line(self, text: str, timeout_s: float = ...) -> str: ...


NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
"""PC -> nRF52840 (comandos de shell en texto plano)."""
NUS_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
"""nRF52840 -> PC (salida del shell, via notify)."""

DEFAULT_SCAN_TIMEOUT_S = 8.0
DEFAULT_COMMAND_TIMEOUT_S = 9.0
"""El propio bridge puede tardar hasta 8s en darse por vencido con el Qorvo
(ventana de timeout de `qorvo <texto>`, ver especificacion del bridge Seccion
7.6); el timeout del lado host debe ser mayor a eso."""

_PROMPT_RE = re.compile(r"bt_nus:~\$\s*")
_BLE_ADDRESS_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


class BleShellTransport:
    """Transporte sincrono sobre el shell NUS del puente nRF52840."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._client: BleakClient | None = None
        self._buffer = ""
        self._prompt_event: asyncio.Event | None = None
        self._last_target: str | None = None
        """Nombre/direccion pasado a `connect()`, para reconectar automaticamente
        si el bridge cierra la conexion por inactividad (confirmado en
        i-mop-qorvo-CLI-script/src/dwm3001c_cli/transport/ble_link.py:
        el bridge desconecta espontaneamente ~7-8s despues de la ultima
        actividad -- no es un bug, es el comportamiento normal del bridge)."""

    def _call(self, coro: Any, timeout: float) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            raise BleShellTimeoutError(f"timeout de {timeout}s esperando la operacion BLE") from exc

    def connect(
        self,
        name_or_address: str,
        *,
        scan_timeout_s: float = DEFAULT_SCAN_TIMEOUT_S,
    ) -> str:
        """Conecta al dispositivo BLE dado por nombre (substring) o direccion MAC.

        Devuelve la direccion BLE efectivamente conectada.
        """
        return cast(
            str,
            self._call(
                self._async_connect(name_or_address, scan_timeout_s),
                timeout=scan_timeout_s + 15.0,
            ),
        )

    async def _async_connect(self, name_or_address: str, scan_timeout_s: float) -> str:
        self._prompt_event = asyncio.Event()

        if _BLE_ADDRESS_RE.match(name_or_address):
            device: Any = name_or_address
        else:
            device = await BleakScanner.find_device_by_filter(
                lambda d, _adv: bool(d.name and name_or_address in d.name),
                timeout=scan_timeout_s,
            )
            if device is None:
                raise BleShellError(
                    f"no se encontro ningun dispositivo BLE con nombre que "
                    f"contenga {name_or_address!r} en {scan_timeout_s}s"
                )

        client = BleakClient(device)
        await client.connect()
        await client.start_notify(NUS_TX_CHAR_UUID, self._handle_notify)
        self._client = client
        self._last_target = name_or_address
        return client.address

    async def _async_ensure_connected(self, scan_timeout_s: float = DEFAULT_SCAN_TIMEOUT_S) -> None:
        """Reconecta automaticamente si el bridge cerro la conexion por inactividad.

        Sin esto, un `send_line` despues de un hueco de inactividad (~7-8s,
        ver nota en `__init__`) fallaria con un `BleShellTimeoutError` ambiguo
        en vez de simplemente reconectar y seguir -- confirmado contra
        hardware real (ver docs/ranging-mixto-cli-uci.md).
        """
        if self._client is not None and self._client.is_connected:
            return
        if self._last_target is None:
            raise BleShellError("no conectado: llamar a connect() primero")
        await self._async_connect(self._last_target, scan_timeout_s)

    def _handle_notify(self, _sender: Any, data: bytearray) -> None:
        text = bytes(data).decode("utf-8", errors="replace")
        self._buffer += text
        if _PROMPT_RE.search(text) and self._prompt_event is not None:
            self._prompt_event.set()

    def disconnect(self) -> None:
        if self._client is not None:
            self._call(self._client.disconnect(), timeout=10.0)
            self._client = None

    def close(self) -> None:
        """Desconecta (si hace falta) y apaga el hilo/loop dedicado."""
        try:
            self.disconnect()
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5.0)

    def send_line(self, text: str, timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S) -> str:
        """Envia una linea de shell y devuelve la respuesta, sin el prompt final."""
        return cast(
            str, self._call(self._async_send_line(text, timeout_s), timeout=timeout_s + 2.0)
        )

    async def _async_send_line(self, text: str, timeout_s: float) -> str:
        await self._async_ensure_connected()
        assert self._client is not None and self._prompt_event is not None

        self._prompt_event.clear()
        start = len(self._buffer)
        payload = (text + "\n").encode("ascii")
        await self._client.write_gatt_char(NUS_RX_CHAR_UUID, payload, response=False)

        try:
            await asyncio.wait_for(self._prompt_event.wait(), timeout=timeout_s)
        except TimeoutError as exc:
            raise BleShellTimeoutError(
                f"sin respuesta del shell BLE tras {timeout_s}s para: {text!r}"
            ) from exc

        raw = self._buffer[start:]
        return _PROMPT_RE.sub("", raw).strip("\r\n")
