"""Puente hacia una placa DWM3001C con firmware CLI de texto, via BLE.

**No es parte del protocolo UCI.** Este subpaquete vive separado de
`transport/`/`uci/`/`core/` (especificos de UCI) porque habla un protocolo
completamente distinto: el shell de Zephyr del puente nRF52840
(`I-mop-nrf52840-fw`) expuesto sobre Nordic UART Service (NUS), que a su vez
reenvia comandos de texto a la CLI del propio Qorvo remoto (`qorvo <texto>`).

Uso experimental: ver `src/dwm3001c_uci/mixed_ranging.py` y
docs/plan-implementacion.md ("ranging mixto UCI+CLI").

Requiere el extra opcional `ble` (`pip install -e .[ble]`, agrega `bleak`).
"""
