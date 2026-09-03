# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Semantic Versioning](https://semver.org/lang/es/) — ver la política completa en [docs/versionado.md](docs/versionado.md).

## [Unreleased]

### Added

- Documentación inicial de arquitectura, protocolo UCI, plan de implementación, flujo de trabajo con Git y política de versionado (`CLAUDE.md`, `docs/`). Todavía no hay código implementado — ver [docs/plan-implementacion.md](docs/plan-implementacion.md).
- Setup del proyecto (fase F0): `pyproject.toml`, layout `src/dwm3001c_uci/` con los paquetes `transport/`, `uci/`, `core/`, `validation/`, `app/`.
- Capa de transporte (fase F1): `SerialLink` (pyserial) y descubrimiento de puertos serie candidatos.
- Framing y enums UCI (fase F2): codificación/decodificación de tramas (`MT`/`PBF`/`GID`/`OID`), fragmentación y reensamblado de mensajes (`StreamDecoder`), y los enums `Gid`, `OidCore`, `OidSession`, `OidRanging`, `OidTest`, `Status` confirmados contra el SDK QM33 1.1.1.
- Valores exactos de `Status` corregidos en `docs/protocolo-uci.md` tras verificarlos por lectura directa de la fuente del SDK (algunos códigos habían quedado mal estimados en el resumen inicial).
- Cliente UCI de alto nivel, grupo `Core` (fase F3): `UciClient.reset()`, `get_device_info()`, `get_caps_raw()`, con correlación comando↔respuesta, timeout configurable y captura de notificaciones intercaladas (`core/client.py`, `core/models.py`, `core/errors.py`).
- Baud rate del transporte serie (115200) confirmado para firmware UCI (antes marcado `[Sin confirmar]`), y validación de extremo a extremo contra una placa DWM3001CDK real: `reset()`, `get_device_info()` y `get_caps_raw()` funcionando contra hardware.
- Cliente UCI de alto nivel, grupo `Session` (fase F4): `UciClient.session_init()`, `session_deinit(session_handle)`, `get_session_state(session_handle)`, `get_session_count()`, con `SESSION_STATUS_NTF` parseada y capturada como el resto de las notificaciones. Enums `SessionType`, `SessionState`, `SessionStateChangeReason`, `DeviceState` agregados a `uci/enums.py`, confirmados contra la fuente del SDK.
- Validación de extremo a extremo del grupo `Session` contra hardware real: ciclo completo `session_init` → `get_session_state` → `get_session_count` → `session_deinit` → `get_session_count`, con las notificaciones `SESSION_STATUS_NTF` esperadas. Hallazgo documentado en `docs/protocolo-uci.md`: el `session_handle` que devuelve `SESSION_INIT` puede ser distinto del `session_id` solicitado — por eso `session_deinit()`/`get_session_state()` reciben explícitamente `session_handle`, no `session_id`.
- Cliente UCI de alto nivel, grupo `Ranging` (fase F5): `UciClient.ranging_start(session_handle)`, `ranging_stop(session_handle)`, `get_ranging_count(session_handle)`.
- Validación de extremo a extremo del grupo `Ranging` contra hardware real (una sola placa disponible): `get_ranging_count()` devuelve `Status.OK`/conteo `0` sobre una sesión recién creada; `ranging_start()`/`ranging_stop()` sobre una sesión sin configurar devuelven `Status.ERROR_SESSION_NOT_CONFIGURED`, confirmando que `SESSION_SET_APP_CONFIG` (diferido) es un prerrequisito real. Un ciclo de ranging exitoso con medición de distancia queda pendiente: requiere `SESSION_SET_APP_CONFIG` y una segunda placa.
- Suite de validación declarativa (fase F6): `validation/spec.py` (`DEFAULT_SPECS`, 11 comandos de `Core`/`Session`/`Ranging`), `validation/runner.py` (`run_checks`) y `validation/report.py` (`render_text`, `to_dict`). `FakeTransport` (`tests/fakes.py`) ahora soporta encadenar varias capturas reales de hardware en secuencia (parámetro `responses`), liberando cada una recién después del `write()` correspondiente.
- Primera corrida completa de la suite contra hardware real: **11/11 checks OK**. Reporte archivado en `docs/validaciones/2026-09-03-validacion-f0-f6.txt` y resumido en `docs/resultados-validacion.md`.
- `session_set_app_config()` (fase F4, alcance ampliado): codec TVS (`uci/app_config.py`, `encode_app_config`) y 15 parámetros de `AppConfigParam` — el conjunto necesario para levantar una sesión de TWR real (más que los 5 que el SDK etiqueta como "mandatory/minimal", ver hallazgo abajo). Enums `AppConfigParam`, `DeviceType`, `DeviceRole`, `MultiNodeMode`, `RangingRoundUsage` agregados a `uci/enums.py`.
- Parseo del header de `RANGING_DATA_NTF` (`core/models.py::parse_ranging_data_notification`, `RangingMeasType` en `uci/enums.py`) — resuelve el `[Sin confirmar]` de F5: confirmado contra hardware real que el firmware emite esta notificación en cada ronda de ranging, incluso sin un segundo dispositivo. Las mediciones individuales dentro de la notificación quedan sin decodificar.
- **Ranging real confirmado contra hardware** (una sola placa, sin par): con la sesión configurada, `ranging_start()` devuelve `Status.OK`, el estado de sesión pasa a `ACTIVE`, y se reciben `RANGING_DATA_NTF` reales en cada ronda. Máquina de estados de sesión confirmada de punta a punta: `INIT` → (`SET_APP_CONFIG`) → `IDLE` → (`RANGING_START`) → `ACTIVE` → (`RANGING_STOP`) → `IDLE` → (`SESSION_DEINIT`) → `DEINIT`.
- **Hallazgo confirmado contra hardware:** los 5 parámetros que `run_fira_twr.py` del SDK etiqueta como "Fira Mandatory/minimal session config" no alcanzan para desbloquear `RANGING_START` (el firmware sigue devolviendo `Status.ERROR_SESSION_NOT_CONFIGURED`); hacen falta 9 parámetros adicionales de timing/PHY, documentados en `docs/protocolo-uci.md` §2.2.
- `docs/referencia-comandos-uci.md`: referencia completa de los 11 comandos implementados — qué hace cada uno, bytes reales de request/response, y el significado de cada parámetro (incluida la tabla de los 15 parámetros de `session_set_app_config()`).

### Changed

- Auditoría completa de la documentación contra el estado real del código (`README.md`, `CLAUDE.md`, `docs/arquitectura.md`): corregidas referencias obsoletas que describían el proyecto como "todavía sin implementar" (F0-F6 ya estaban completos), inventario de módulos desactualizado (`uci/codec.py` nunca existió; los modelos de datos por comando viven en `core/models.py`), lista de excepciones y de métodos de `UciClient` desactualizada, y el baud rate que seguía marcado `[Sin confirmar]` pese a estar confirmado desde F1.
- Investigado si el banco BLE (`UWB-Node-N`) del proyecto hermano `i-mop-qorvo-CLI-script` podía usarse como segunda placa para ranging real: **no sirve tal cual** — corre firmware CLI de texto sobre un puente nRF52840 (protocolo Nordic UART Service, no framing UCI), y su USB queda inaccesible mientras esté montada en ese puente. Documentado en `docs/plan-implementacion.md` ("Trabajo futuro") y `CLAUDE.md` §1.2.

### Fixed

- Bug en el reensamblado de mensajes fragmentados (`StreamDecoder`): usaba el tipo `UciPacket` para el acumulador en progreso, lo que rechazaba mensajes reensamblados de más de 255 bytes por una validación pensada para un paquete físico, no para el mensaje lógico completo.
- Bug en `UciClient`: al encontrar la `Response` esperada dentro de un lote de mensajes ya decodificados, retornaba de inmediato y descartaba notificaciones del mismo lote que todavía no se habían procesado (reproducido contra hardware real: dos `DEVICE_STATUS_NTF` intercaladas con la respuesta de `CORE_RESET`).
