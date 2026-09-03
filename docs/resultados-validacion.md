# Resultados de validación — F0 a F6

> **Propósito:** dejar constancia de las corridas de la suite de validación (`validation/`, `DEFAULT_SPECS`) contra hardware real, y del estado de cobertura de comandos UCI alcanzado en las fases F0–F6.
> **Alcance:** grupos `Core`, `Session` y `Ranging` (comandos ya implementados en `core/client.py`). `DEFAULT_SPECS` en sí no cubre `set_app_config`/`get_app_config` ni un ciclo de ranging con medición de distancia (ver [plan-implementacion.md](plan-implementacion.md) F6) — **eso sí se validó por separado**, con `session_set_app_config()` y `mixed_ranging.py` contra una segunda placa, ver [ranging-mixto-cli-uci.md](ranging-mixto-cli-uci.md).

## 1. Entorno de la corrida

| Campo | Valor |
|---|---|
| Fecha | 2026-09-03 |
| Placa | DWM3001CDK (puerto COM29, USB CDC ACM) |
| Firmware | `*-UCI-FreeRTOS.hex`, release `QM33SDK-1.1.1` |
| Versión de `dwm3001c-uci` | 0.1.0 |
| Cantidad de placas disponibles | 1 (no permite validar un ciclo de ranging real entre `Controller`/`Controlee`) |
| Reporte crudo | [validaciones/2026-09-03-validacion-f0-f6.txt](validaciones/2026-09-03-validacion-f0-f6.txt) |

## 2. Resultado

**11/11 checks OK** (`DEFAULT_SPECS` de `validation/spec.py`, ejecutados con `validation.runner.run_checks`):

| Check | Resultado | Nota |
|---|---|---|
| `CORE_RESET` | OK | `Status.OK` |
| `CORE_GET_DEVICE_INFO` | OK | `uci_version=2.0.0`, `mac_version=2.0.0`, `phy_version=2.0.0`, `uci_test_version=1.1.0` |
| `CORE_GET_CAPS` | OK | `Status.OK`, 93 bytes de payload TLV sin decodificar |
| `SESSION_INIT` | OK | `session_handle` devuelto por el firmware: `1` |
| `SESSION_GET_STATE` | OK | `SessionState.INIT` |
| `SESSION_GET_COUNT` (sesión activa) | OK | `count=1` |
| `RANGING_GET_COUNT` | OK | `count=0` |
| `RANGING_START` | OK | `Status.ERROR_SESSION_NOT_CONFIGURED` — resultado **esperado**: la sesión nunca se configuró con `SESSION_SET_APP_CONFIG` (no implementado, ver F4) |
| `RANGING_STOP` | OK | `Status.ERROR_SESSION_NOT_CONFIGURED`, coherente con el paso anterior |
| `SESSION_DEINIT` | OK | `Status.OK` |
| `SESSION_GET_COUNT` (vacía) | OK | `count=0`, confirma que `SESSION_DEINIT` liberó la sesión |

## 3. Hallazgos de firmware/protocolo confirmados durante F0–F6

Documentados en detalle en [protocolo-uci.md](protocolo-uci.md) y en el `CHANGELOG.md`; resumen:

- Baud rate del firmware UCI: **115200** (confirmado, no es solo herencia del firmware CLI).
- `CORE_RESET` requiere payload de 1 byte (`0x00`); con payload vacío el firmware responde `SYNTAX_ERROR`.
- El `session_handle` que devuelve `SESSION_INIT` **puede ser distinto** del `session_id` solicitado por el host — usar el `session_id` original en comandos posteriores devuelve `ERROR_SESSION_NOT_EXIST`.
- `CORE_RESET` limpia sesiones activas colgadas de una corrida anterior (emite `SESSION_STATUS_NTF` a `DEINIT` por cada una).
- `RANGING_START` sobre una sesión sin `SESSION_SET_APP_CONFIG` devuelve `ERROR_SESSION_NOT_CONFIGURED` — confirma que ese comando es un prerrequisito real (implementado después de esta corrida, ver F4 en [plan-implementacion.md](plan-implementacion.md)).
- Existen valores de `MT` (`0b100`/`0b101`) no cubiertos por el framing estándar, usados para mensajes de test — fuera de alcance mientras no se implemente el grupo `Test`.

## 4. Corrida de re-validación tras un cambio de firmware UCI (2026-09-03)

El usuario actualizó el firmware UCI de la placa local (`COM29`) y pidió repetir la validación para confirmar que el firmware nuevo no rompió nada. Se repitió exactamente la misma suite (`DEFAULT_SPECS`, sin cambios) y, por separado, `mixed_ranging.py` para confirmar también la medición de distancia real.

**Resultado: 11/11 checks OK, idéntico a la corrida original.** Reporte archivado en [validaciones/2026-09-03-validacion-post-firmware-update.txt](validaciones/2026-09-03-validacion-post-firmware-update.txt). La medición de distancia real (`mixed_ranging.py`, ver [ranging-mixto-cli-uci.md](ranging-mixto-cli-uci.md)) también siguió funcionando: 2/45 rondas con distancia real medida, el resto `RANGING_NEGATIVE_DISTANCE` — esperable con las placas muy cerca y sin calibración de retardo de antena (fuera de alcance de este proyecto, ver `CLAUDE.md`), no una regresión.

## 5. Pendiente para una próxima corrida

- `SESSION_GET_APP_CONFIG` y el resto de los ~64 parámetros de `App.defs` no implementados todavía (ver [protocolo-uci.md §2.2](protocolo-uci.md#22-session_set_app_config-bloque-tvs-y-máquina-de-estados-confirmada)).
- Extender `DEFAULT_SPECS` (`validation/spec.py`) para que también ejercite `SESSION_SET_APP_CONFIG` y espere `Status.OK` de `RANGING_START` — hoy esa spec deliberadamente no configura la sesión (ver docstring del módulo), así que sigue validando el camino "sesión sin configurar" en vez del camino real de ranging, que ya está cubierto por separado en `docs/ranging-mixto-cli-uci.md`.
- Validar un ciclo de ranging real entre dos placas que corran **ambas** firmware UCI (sin CLI/BLE de por medio) — ver nota en `plan-implementacion.md`.
