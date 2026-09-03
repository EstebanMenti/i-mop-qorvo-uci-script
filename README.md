# dwm3001c-uci

> Herramienta de línea de comandos en **Python** para probar la comunicación **UCI** (Ultra-Wideband Command Interface, protocolo binario basado en FiRa) con el módulo UWB **Qorvo DWM3001C**, cuando la placa de desarrollo **DWM3001CDK** corre el **firmware UCI** del SDK QM33 (release de referencia: `QM33SDK-1.1.1`, variante `*-UCI-FreeRTOS.hex`).

## Estado del proyecto

**Núcleo implementado y validado contra hardware real (fases F0–F6 del plan), incluyendo medición de distancia real.** El transporte serie, el framing UCI y el cliente de alto nivel (`UciClient`) para los grupos `Core`, `Session` y `Ranging` funcionan y se probaron contra una placa DWM3001CDK real, incluyendo `SESSION_SET_APP_CONFIG` con 26 parámetros y un ciclo de ranging real completo (`RANGING_START` → rondas activas → `RANGING_STOP`). **Se logró además una medición de distancia real** contra una segunda placa (con firmware CLI, controlada por Bluetooth vía `cli_bridge/`+`mixed_ranging.py`) — ver [docs/ranging-mixto-cli-uci.md](docs/ranging-mixto-cli-uci.md). Ver el detalle exacto de qué se probó en [docs/resultados-validacion.md](docs/resultados-validacion.md) y comando por comando en [docs/referencia-comandos-uci.md](docs/referencia-comandos-uci.md).

**Todavía no implementado / fuera de alcance actual:**
- La interfaz de línea de comandos (`dwm-uci`, fase F7) — por ahora la herramienta se usa como biblioteca Python (`import dwm3001c_uci`) desde scripts propios, sin CLI.
- Un ciclo de ranging real entre dos placas que corran **ambas** firmware UCI (sin CLI/BLE de por medio) — la medición de distancia lograda hasta ahora usa una segunda placa con firmware CLI.
- Calibración de retardo de antena — fuera de alcance de este proyecto en su fase inicial (ver `CLAUDE.md`); sin ella, la distancia medida tiene un sesgo real.
- `SESSION_GET_APP_CONFIG` y la decodificación completa de `CORE_GET_CAPS`/las mediciones individuales de `RANGING_DATA_NTF` cuando hay más de un `Controlee`.

El plan de implementación completo por fases está en [docs/plan-implementacion.md](docs/plan-implementacion.md).

## Qué hace

1. **Probar la comunicación UCI de punta a punta**: abre el puerto serie de la placa, envía comandos UCI (`CORE_RESET`, `CORE_GET_DEVICE_INFO`, `CORE_GET_CAPS`, `SESSION_INIT`, `SESSION_SET_APP_CONFIG`, `RANGING_START`, etc.) y decodifica las respuestas y notificaciones — ver [docs/referencia-comandos-uci.md](docs/referencia-comandos-uci.md) para el detalle de cada uno.
2. **Automatizar una suite de validación** (`validation/`) de esos comandos, generando un reporte de resultados (análogo al objetivo de validación de [i-mop-qorvo-CLI-script](https://github.com/EstebanMenti/i-mop-qorvo-CLI-script), pero contra el protocolo binario en lugar de la consola de texto).
3. **Medir distancia real** entre esta placa (UCI, `Controller`/`Initiator`) y una segunda placa DWM3001CDK con firmware CLI, controlada por Bluetooth a través de un puente nRF52840 (`cli_bridge/` + `mixed_ranging.py`) — ver [docs/ranging-mixto-cli-uci.md](docs/ranging-mixto-cli-uci.md).

No es un reemplazo del script CLI existente: ese proyecto habla con el firmware **CLI** de texto; este habla con el firmware **UCI** binario del mismo SDK. Son firmwares distintos (`*-CLI-FreeRTOS.hex` vs `*-UCI-FreeRTOS.hex`) que no corren simultáneamente en la misma placa.

## Hardware requerido

- Placa **DWM3001CDK** con el firmware `*-UCI-FreeRTOS.hex` de `QM33SDK-1.1.1` flasheado.
- Cable USB — la placa expone un puerto COM virtual (USB CDC ACM), a 115200 8N1 (confirmado).
- Opcional, para ranging real: una segunda placa DWM3001CDK con firmware **CLI**, accesible por Bluetooth a través de un puente nRF52840 (Nordic UART Service) — no hace falta una segunda placa UCI dedicada. Requiere el extra `pip install -e .[ble]` (`bleak`). Ver [docs/ranging-mixto-cli-uci.md](docs/ranging-mixto-cli-uci.md).

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Uso actual (como biblioteca Python — todavía no hay CLI)

```python
from dwm3001c_uci.transport.serial_link import SerialLink
from dwm3001c_uci.core.client import UciClient

with SerialLink("COM29") as link:
    client = UciClient(link)
    client.reset()
    info = client.get_device_info()
    print(info.uci_version, info.mac_version, info.phy_version)
```

Para correr la suite de validación completa contra una placa conectada:

```python
from dwm3001c_uci.validation.spec import DEFAULT_SPECS
from dwm3001c_uci.validation.runner import run_checks
from dwm3001c_uci.validation.report import render_text

outcomes = run_checks(client, DEFAULT_SPECS)
print(render_text(outcomes))
```

La futura CLI (`dwm-uci ports/info/validate`, fase F7) se documenta acá en el mismo PR que la implemente (ver regla de sincronización en [CLAUDE.md](CLAUDE.md#4-reglas-de-documentación)).

## Documentación

Punto de entrada completo: [docs/README.md](docs/README.md). Para empezar:

| Si querés... | Leé |
|---|---|
| Entender las reglas de contribución, dominio y flujo de trabajo | [CLAUDE.md](CLAUDE.md) |
| Entender el diseño del software (capas, módulos) | [docs/arquitectura.md](docs/arquitectura.md) |
| Entender el protocolo UCI (framing, comandos, estados) | [docs/protocolo-uci.md](docs/protocolo-uci.md) |
| Ver qué hace cada comando, con bytes reales y parámetros | [docs/referencia-comandos-uci.md](docs/referencia-comandos-uci.md) |
| Ver el plan de implementación por fases | [docs/plan-implementacion.md](docs/plan-implementacion.md) |
| Ver qué se validó contra hardware real y cuándo | [docs/resultados-validacion.md](docs/resultados-validacion.md) |
| Medir distancia real con una segunda placa (CLI, por BLE) | [docs/ranging-mixto-cli-uci.md](docs/ranging-mixto-cli-uci.md) |
| Entender cómo se versiona y publica el proyecto | [docs/versionado.md](docs/versionado.md) |

## Licencia

Uso interno — ver [LICENSE](LICENSE).
