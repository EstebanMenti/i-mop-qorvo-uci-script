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
- **Tarea de investigación obligatoria:** confirmar contra la documentación del SDK los parámetros de puerto serie del binario `*-UCI-FreeRTOS.hex` (baud rate, bits, paridad, control de flujo) — no asumir los valores del firmware CLI. Documentar el resultado en [protocolo-uci.md §5](protocolo-uci.md#5-transporte), reemplazando el `[Sin confirmar]`.
- Implementar `FakeTransport` en `tests/fakes.py` para uso de las fases siguientes.

**Aceptación:** se puede abrir el puerto de una placa con firmware UCI real y leer/escribir bytes crudos; parámetros de puerto documentados y confirmados.

## F2 — Framing y enums UCI

- Implementar `uci/enums.py` (`MessageType`, `Gid`, `OidCore`, `OidSession`, `OidRanging`, `OidTest`, `Status`) según [protocolo-uci.md §2 y §4](protocolo-uci.md#2-grupos-de-comando-gid-y-opcodes-oid).
- Implementar `uci/framing.py`: codificación de mensaje lógico → bytes, y reensamblado de tramas fragmentadas (`PBF`) → mensaje lógico.
- Tests con tramas reales (capturadas con la placa, o al menos con `decode_uci` del SDK como referencia de bytes válidos) para: mensaje simple, mensaje fragmentado, `Status` de error.

**Aceptación:** codec de framing con cobertura de tests incluyendo fragmentación; ningún test requiere hardware.

## F3 — Cliente UCI: grupo `Core`

- Implementar `core/client.py` (`UciClient`) con los comandos `Core`: `reset()`, `get_device_info()`, `get_caps()`, `set_config()`, `get_config()`.
- Implementar correlación comando↔respuesta con timeout configurable, y despacho de notificaciones (`DEVICE_STATUS_NTF`, `GENERIC_ERROR_NTF`) por un canal separado.
- Implementar `core/errors.py` (`UciError`, `UciTimeoutError`, `UciStatusError`, `UciFramingError`) y `core/models.py` (`DeviceInfo`, `Capabilities`).

**Aceptación:** contra hardware real, `get_device_info()` y `get_caps()` devuelven datos coherentes con lo esperado del chip DW3xxx; tests unitarios con `FakeTransport` cubren el camino feliz y al menos un `Status` de error.

## F4 — Cliente UCI: grupo `Session`

- Extender `UciClient` con `session_init()`, `session_deinit()`, `set_app_config()`, `get_app_config()`, `get_session_state()`.
- Parsear `SESSION_STATUS_NTF` y exponerlo vía el canal de notificaciones.
- Confirmar contra la especificación (o contra el comportamiento observado en hardware) la máquina de estados relevante antes de codificarla como supuesto en el cliente — documentar hallazgos en `protocolo-uci.md`.

**Aceptación:** se puede inicializar una sesión contra hardware real y observar la transición de estado esperada vía `SESSION_STATUS_NTF`.

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
