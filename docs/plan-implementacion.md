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
- **Pendiente:** `set_app_config()`, `get_app_config()`, `update_multicast_list()` y el resto de los OID de `Session` — su payload usa una codificación TVS genérica ligada a una tabla de parámetros de aplicación (`App.defs` en el SDK de referencia) que todavía no se relevó; queda para una iteración siguiente en vez de adivinar el formato.
- **Hallazgo importante confirmado contra hardware real:** el `session_handle` que devuelve `SESSION_INIT` **puede ser distinto** del `session_id` que el host propuso en el comando (se probó pidiendo `session_id=7` y el firmware asignó `session_handle=1`). Todos los comandos posteriores de `Session` (`GET_STATE`, `DEINIT`, ...) deben usar el `session_handle` devuelto, no el `session_id` original — usar el original devuelve `Status.ERROR_SESSION_NOT_EXIST`. Por eso `session_deinit()`/`get_session_state()` en `core/client.py` toman un parámetro `session_handle`, no `session_id`. Esto contradice la suposición implícita del cliente Python de referencia de Qorvo (`fira.py`), que reutiliza la misma variable `sid` para todo — no se debe copiar ese supuesto sin verificar.
- También se confirmó que `CORE_RESET` limpia sesiones activas (emite `SESSION_STATUS_NTF` a `DEINIT` para cualquier sesión colgada de una corrida anterior).

**Aceptación:** ✅ validado contra hardware real: `session_init()` → `Status.OK`, `get_session_state(handle)` → `Status.OK` con `SessionState.INIT`, `get_session_count()` refleja la sesión activa (1) y luego su ausencia (0) tras `session_deinit(handle)`. Se capturan las 2 notificaciones `SESSION_STATUS_NTF` esperadas (`INIT` y `DEINIT`), con `reason_code=0` (`STATE_CHANGE_WITH_SESSION_MANAGEMENT_COMMANDS`), coincidiendo con `SessionState`/`SessionStateChangeReason` de `uci/enums.py`.

## F5 — Cliente UCI: grupo `Ranging`

- Extender `UciClient` con `ranging_start()`, `ranging_stop()`, `get_ranging_count()`.
- Parsear las notificaciones de datos de ranging (nombre/formato a confirmar, ver [protocolo-uci.md §3](protocolo-uci.md#3-notificaciones-a-manejar-de-forma-asíncrona)).

**Aceptación:** con dos placas (`Controller`/`Controlee`), se completa un ciclo de ranging real y se recibe al menos una medición vía notificación, decodificada a un `RangingData` con distancia.

## F6 — Suite de validación

- Implementar `validation/spec.py` (spec declarativa: comando, parámetros, `Status` esperado, aserciones sobre el payload), `validation/runner.py` (ejecuta la spec contra un `UciClient`) y `validation/report.py` (genera el reporte).
- Cubrir como mínimo todos los comandos `Core` y `Session` de F3/F4, y los de `Ranging` de F5.

**Aceptación:** `dwm-uci validate` corre contra hardware real, produce un reporte con resultado por comando, y el resultado se archiva en `docs/validaciones/` (evidencia fechada), siguiendo el patrón de `i-mop-qorvo-CLI-script`.

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
