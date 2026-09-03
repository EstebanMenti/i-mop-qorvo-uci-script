# Plan de implementación

> **Propósito:** definir las fases de implementación del paquete `dwm3001c_uci`, con criterios de aceptación por fase, para que cualquier desarrollador o asistente de IA pueda continuar el trabajo sin perder de vista el diseño acordado.
> **Alcance:** desde la fase F0 (setup) hasta una primera suite de validación de comandos UCI funcionando contra hardware real. No incluye calibración de antena ni extensiones propietarias de Qorvo (ver [protocolo-uci.md §6](protocolo-uci.md#6-extensiones-propietarias-de-qorvo)), que quedan como trabajo futuro.

---

## Cómo usar este plan

- Cada fase produce una rama `feature/...` con su propio PR (ver flujo de Git en [../CLAUDE.md §5](../CLAUDE.md#5-flujo-de-trabajo-con-git)).
- Ninguna fase se da por completa sin que sus **criterios de aceptación** estén verificados y, cuando corresponda, documentados en `docs/` (resultado real capturado, no solo "debería funcionar").
- Si una fase revela que un supuesto del diseño (`docs/arquitectura.md`, `docs/protocolo-uci.md`) era incorrecto, se corrige el documento correspondiente en el mismo PR.

## F0 — Setup del proyecto

- Crear `pyproject.toml` (PEP 621) con metadatos, dependencias base (`pyserial`, `typer`, `rich`) y configuración de `ruff`/`mypy`/`pytest`.
- Crear el layout `src/dwm3001c_uci/` con los paquetes vacíos `transport/`, `uci/`, `core/`, `validation/`, `app/` (con `__init__.py`).
- Configurar `pytest` con el marker `hardware` y exclusión por defecto (`-m "not hardware"`).

**Aceptación:** `pip install -e .[dev]` funciona; `ruff check`, `mypy src`, `pytest` corren sin errores sobre un proyecto vacío.

## F1 — Transporte serie

- Implementar `transport/serial_link.py` (apertura/cierre, lectura no bloqueante, escritura) y `transport/discovery.py` (enumeración de puertos candidatos).
- ~~Tarea de investigación obligatoria: confirmar baud rate contra el SDK~~ — **hecho:** 115200, confirmado contra `addin_transport_uart.py` (ver [protocolo-uci.md §5](protocolo-uci.md#5-transporte)). Bits/paridad no vienen explícitos en esa fuente; se usa 8N1 (default de pyserial) hasta que una prueba real indique lo contrario.
- Implementar `FakeTransport` en `tests/fakes.py` para uso de las fases siguientes.

**Aceptación:** se puede abrir el puerto de una placa con firmware UCI real y leer/escribir bytes crudos; parámetros de puerto documentados y confirmados. **Pendiente:** validar contra hardware real que el firmware efectivamente cargado en la placa disponible es `*-UCI-FreeRTOS.hex` (una placa DWM3001CDK puede tener cualquier firmware del SDK cargado).

## F2 — Framing y enums UCI

- Implementar `uci/enums.py` (`MessageType`, `Gid`, `OidCore`, `OidSession`, `OidRanging`, `OidTest`, `Status`) según [protocolo-uci.md §2 y §4](protocolo-uci.md#2-grupos-de-comando-gid-y-opcodes-oid).
- Implementar `uci/framing.py`: codificación de mensaje lógico → bytes, y reensamblado de tramas fragmentadas (`PBF`) → mensaje lógico.
- Tests con tramas reales (capturadas con la placa, o al menos con `decode_uci` del SDK como referencia de bytes válidos) para: mensaje simple, mensaje fragmentado, `Status` de error.

**Aceptación:** codec de framing con cobertura de tests incluyendo fragmentación; ningún test requiere hardware.

## F3 — Cliente UCI: grupo `Core`

- ✅ `core/client.py` (`UciClient`) con `reset()`, `get_device_info()`, `get_caps_raw()` — correlación comando↔respuesta con timeout configurable, y notificaciones (`DEVICE_STATUS_NTF`) capturadas en `UciClient.notifications` en vez de descartadas.
- ✅ `core/errors.py` (`UciError`, `UciTimeoutError`, `UciStatusError`, `UciPayloadError`) y `core/models.py` (`DeviceInfo`, `VersionTriplet`, `parse_device_info`).
- **Pendiente:** `set_config()`, `get_config()` (no probados todavía) y decodificación completa de la lista TLV de `get_caps_raw()` (por ahora devuelve `(Status, bytes)` sin parsear) — quedan para una iteración siguiente.

**Aceptación:** ✅ validado contra hardware real (placa en `COM29`, firmware UCI de `QM33SDK-1.1.1`): `reset()` devuelve `Status.OK` y captura 2 notificaciones `DEVICE_STATUS_NTF` intercaladas; `get_device_info()` devuelve `uci_version=2.0.0`, `mac_version=2.0.0`, `phy_version=2.0.0`, `uci_test_version=1.1.0`; `get_caps_raw()` devuelve `Status.OK` y 93 bytes de payload TLV. 40 tests unitarios con `FakeTransport`, usando capturas reales de estos tres intercambios como fixtures (no datos sintéticos). Hallazgo registrado: `CORE_RESET` requiere payload de 1 byte (`0x00`), no vacío — confirmado contra `fira.py` del SDK y contra hardware.

## F4 — Cliente UCI: grupo `Session`

- ✅ `UciClient` extendido con `session_init()`, `session_deinit()`, `get_session_state()`, `get_session_count()`. Notificaciones `SESSION_STATUS_NTF` parseadas (`core/models.py`, `parse_session_status_notification`) y capturadas en `UciClient.notifications` igual que las de `Core`.
- ✅ `session_set_app_config()` — alcance mínimo ampliado (ver docs/protocolo-uci.md §2.2): 15 parámetros (`uci/app_config.py`, `AppConfigParam`), suficientes para levantar una sesión de TWR real, confirmado contra hardware. `get_app_config()`, `update_multicast_list()` y el resto de los ~90 parámetros de `App.defs` quedan pendientes.
- **Hallazgo importante confirmado contra hardware real:** el `session_handle` que devuelve `SESSION_INIT` **puede ser distinto** del `session_id` que el host propuso en el comando (se probó pidiendo `session_id=7` y el firmware asignó `session_handle=1`). Todos los comandos posteriores de `Session` (`GET_STATE`, `DEINIT`, `SET_APP_CONFIG`, ...) deben usar el `session_handle` devuelto, no el `session_id` original — usar el original devuelve `Status.ERROR_SESSION_NOT_EXIST`. Esto contradice la suposición implícita del cliente Python de referencia de Qorvo (`fira.py`), que reutiliza la misma variable `sid` para todo — no se debe copiar ese supuesto sin verificar.
- También se confirmó que `CORE_RESET` limpia sesiones activas (emite `SESSION_STATUS_NTF` a `DEINIT` para cualquier sesión colgada de una corrida anterior).

**Aceptación:** ✅ validado contra hardware real: `session_init()` → `Status.OK`, `get_session_state(handle)` → `Status.OK` con `SessionState.INIT`, `get_session_count()` refleja la sesión activa (1) y luego su ausencia (0) tras `session_deinit(handle)`. Se capturan las 2 notificaciones `SESSION_STATUS_NTF` esperadas (`INIT` y `DEINIT`), con `reason_code=0` (`STATE_CHANGE_WITH_SESSION_MANAGEMENT_COMMANDS`), coincidiendo con `SessionState`/`SessionStateChangeReason` de `uci/enums.py`. ✅ `session_set_app_config()` con los 15 parámetros mínimos devuelve `Status.OK` sin rechazos, y **desbloquea `RANGING_START` de verdad** (ver F5).

## F5 — Cliente UCI: grupo `Ranging`

- ✅ `UciClient` extendido con `ranging_start(session_handle)`, `ranging_stop(session_handle)`, `get_ranging_count(session_handle)` — mismo patrón de payload que `Session` (`session_handle`, 4 bytes LE), confirmado contra `fira.py` del SDK y contra hardware real.
- ✅ **`RANGING_DATA_NTF` confirmado y su header parseado** (`core/models.py::parse_ranging_data_notification`, 25 bytes de header + mediciones sin decodificar) — ya no es `[Sin confirmar]`: se verificó contra hardware real que el firmware la emite en cada ronda de ranging (`GID=0x02`, `OID=0x00` igual que `RANGING_START`, `MT=NOTIFICATION`), **incluso con una sola placa sin par que responda**. Las mediciones individuales (dependen de `RangingMeasType`, p. ej. TWR) quedan pendientes.
- ✅ `SESSION_SET_APP_CONFIG` (ver F4) implementado y confirmado como prerrequisito real y suficiente (con el conjunto de 15 parámetros) para que `RANGING_START` tenga éxito.

**Aceptación:** ✅ validado contra hardware real de punta a punta, con sesión configurada: `ranging_start()` → `Status.OK`, el estado de sesión pasa a `SessionState.ACTIVE`, se ejecutan rondas de ranging reales (9 rondas en ~1 segundo con `ranging_interval_ms=200`, confirmado con `get_ranging_count()`) y se reciben `RANGING_DATA_NTF` reales en cada una (header decodificado correctamente: `session_handle` y `ranging_interval_ms` coinciden exactamente con lo configurado). `ranging_stop()` → `Status.OK`, estado vuelve a `SessionState.IDLE`. **Con solo los 5 parámetros "mandatory" (sin el resto del conjunto mínimo ampliado), `RANGING_START` seguía devolviendo `Status.ERROR_SESSION_NOT_CONFIGURED`** — hallazgo documentado en protocolo-uci.md §2.2. **No se validó** una medición de distancia real entre dos dispositivos (`Controller`/`Controlee`): eso requiere una segunda placa, pendiente para una iteración futura. Tampoco se decodificaron las mediciones individuales dentro de `RANGING_DATA_NTF`.

## F6 — Suite de validación

- ✅ `validation/spec.py` (`CommandSpec`: `run`/`validate` sobre un `context` compartido entre pasos, para specs que dependen de un resultado anterior como `session_handle`), `validation/runner.py` (`run_checks`, nunca interrumpe la corrida por una excepción de un spec — la reporta como check fallido) y `validation/report.py` (`render_text`, `to_dict`).
- ✅ `DEFAULT_SPECS` cubre los 11 comandos de `Core`/`Session`/`Ranging` implementados en F3–F5.
- **Nota de diseño:** `dwm-uci validate` (la CLI) todavía no existe — es la fase F7. Esta fase corrió la suite con un script directo (`run_checks(client, DEFAULT_SPECS)`), no con el comando de consola.

**Aceptación:** ✅ validado contra hardware real: **11/11 checks OK**. Reporte archivado en [docs/validaciones/2026-09-03-validacion-f0-f6.txt](validaciones/2026-09-03-validacion-f0-f6.txt) y resumido en [docs/resultados-validacion.md](resultados-validacion.md), siguiendo el patrón de `i-mop-qorvo-CLI-script`. `RANGING_START`/`RANGING_STOP` validan `Status.ERROR_SESSION_NOT_CONFIGURED` como resultado esperado (no `Status.OK`) porque `SESSION_SET_APP_CONFIG` todavía no está implementado — la spec deja explícito en un comentario que debe actualizarse cuando eso cambie.

## F7 — CLI y logging

- Implementar `app/cli.py` (Typer) con los subcomandos `ports`, `info`, `validate`; `app/logging_setup.py` con logging a archivo del tráfico serie crudo en hex.
- Actualizar `README.md` con la interfaz real (reemplazando "uso previsto" por uso confirmado).

**Aceptación:** `dwm-uci --help` documenta correctamente los subcomandos; una corrida real queda registrada en `logs/` en hex, apta para diagnóstico.

## F8 — Documentación de resultados

- Documentar en `docs/resultados-validacion.md` (nuevo, agregar al índice) el resultado de una campaña de validación contra hardware real, con el mismo formato que `resultados-validacion.md` de `i-mop-qorvo-CLI-script`.
- Cerrar todos los `[Sin confirmar]` que hayan quedado pendientes en `protocolo-uci.md`, o dejarlos explícitamente para una fase futura con justificación.

**Aceptación:** no quedan `[Sin confirmar]` sin resolución explícita en la documentación del protocolo core (`Core`/`Session`/`Ranging`).

## Trabajo futuro (fuera de este plan)

- Extensiones propietarias de Qorvo (calibración, test de RF) — ver [protocolo-uci.md §6](protocolo-uci.md#6-extensiones-propietarias-de-qorvo).
- Transporte alternativo (p. ej. puente BLE), si se replica el patrón de la rama `hardware/ble-bridge-nrf52840` del proyecto hermano.
