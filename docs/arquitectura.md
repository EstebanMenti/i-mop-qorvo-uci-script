# Arquitectura del software

> **Propósito:** definir el diseño de capas del paquete `dwm3001c_uci`, las responsabilidades de cada módulo y las reglas de dependencia entre ellos.
> **Alcance:** diseño de referencia, ya implementado para las fases F0–F6 (ver estado real del proyecto en [../README.md](../README.md) y [plan-implementacion.md](plan-implementacion.md)). Este documento se mantiene sincronizado con el código — si algo cambia, se actualiza en el mismo PR.

---

## 1. Objetivo de diseño

El software debe poder:

1. Enviar y recibir tramas **UCI** binarias por un transporte serie, reensamblando fragmentos (`PBF`) en mensajes completos.
2. Correlacionar cada `Command` con su `Response`, y despachar las `Notification` por un canal separado (pueden llegar de forma asíncrona, sin relación 1:1 con un comando).
3. Ofrecer una API de alto nivel por grupo de comando (`Core`, `Session`, `Ranging`, ...) que use nombres simbólicos, no bytes crudos.
4. Ejecutar una suite de validación declarativa de comandos y producir un reporte, sin acoplar esa suite a Typer/Rich ni al transporte concreto.
5. Ser testeable sin hardware: toda la lógica por encima del transporte debe poder ejercitarse con tramas capturadas reales.

Este diseño reproduce, adaptado a un protocolo binario, el patrón de 4+1 capas de [i-mop-qorvo-CLI-script](https://github.com/EstebanMenti/i-mop-qorvo-CLI-script) (`transport → core → {validation, calibration} → app`), separando además la capa de framing/protocolo (`uci/`) de la capa de cliente de alto nivel (`core/`), porque en UCI el parseo de bytes es sustancialmente más complejo que en una consola de texto.

## 2. Diagrama de capas

```
                      ┌─────────────────────┐
                      │        app/         │  Typer + Rich — único punto de I/O con el usuario
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │    validation/       │  spec declarativa + runner + reporte
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │       core/          │  UciClient: comandos de alto nivel, correlación
                      │                      │  cmd↔resp, cola de notificaciones
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │        uci/          │  framing (MT/PBF/GID/OID/len), enums, codec
                      │                      │  de payload — puro, sin I/O
                      └──────────┬──────────┘
                                 │
                      ┌──────────▼──────────┐
                      │     transport/       │  SerialLink (pyserial), descubrimiento de puertos
                      └─────────────────────┘
```

**Regla de dependencia:** cada capa solo conoce la capa inmediatamente inferior. Ninguna capa por debajo de `app/` importa Typer ni Rich. `transport/` no conoce el protocolo UCI (mueve bytes, nada más). `uci/` no conoce el transporte concreto ni realiza I/O — es lógica pura de codificación/decodificación, lo que la hace trivial de testear.

## 3. Responsabilidad de cada módulo

### 3.1 `transport/`

- `serial_link.py`: apertura/cierre del puerto serie, lectura no bloqueante de bytes crudos, escritura de bytes. No interpreta el contenido.
- `discovery.py`: enumeración de puertos serie candidatos (por VID/PID del adaptador USB CDC ACM de la placa, cuando se confirme cuál es).
- Expone una interfaz mínima (`read(n) -> bytes`, `write(data: bytes) -> None`) para que `uci/` y `core/` puedan testearse contra un `FakeTransport` que reproduce bytes capturados.

### 3.2 `uci/`

- `enums.py`: `MessageType` (Command/Response/Notification/Data), `Gid`, `OidCore`, `OidSession`, `OidRanging`, `OidTest`, `Status`, `SessionType`, `SessionState`, `SessionStateChangeReason`, `DeviceState`, `AppConfigParam`, `DeviceType`, `DeviceRole`, `MultiNodeMode`, `RangingRoundUsage`, `RangingMeasType` — ver tablas completas en [protocolo-uci.md](protocolo-uci.md).
- `framing.py`: codificación de un mensaje lógico (`MT`, `PBF`, `GID`, `OID`, payload) a bytes de trama(s), y el camino inverso: reensamblado de tramas fragmentadas (`PBF`) en un mensaje lógico completo antes de exponerlo (`StreamDecoder`). También define `UciFramingError` (excepción propia de esta capa, no hereda de `UciError` de `core/`).
- `app_config.py`: codec **TVS** (Tag-Value-Size) del bloque de parámetros de `SESSION_SET_APP_CONFIG` (`encode_app_config`) — es el único "codec de payload" que vive en esta capa; el resto de los payloads por comando se decodifican en `core/models.py` (ver más abajo, es una desviación deliberada del diseño original de este documento: la mayoría de los formatos de payload no son genéricos como TVS, así que decodificarlos junto al cliente que los usa resultó más simple que un `uci/codec.py` separado).
- Módulo puro: sin sockets, sin puertos serie, sin logging de I/O. Recibe y devuelve bytes/objetos de datos (`dataclass`).

### 3.3 `core/`

- `client.py`: `UciClient` — API de alto nivel. Grupo `Core`: `reset()`, `get_device_info()`, `get_caps_raw()`. Grupo `Session`: `session_init(session_id, session_type)`, `session_set_app_config(session_handle, ...)`, `session_deinit(session_handle)`, `get_session_state(session_handle)`, `get_session_count()`. Grupo `Ranging`: `ranging_start(session_handle)`, `ranging_stop(session_handle)`, `get_ranging_count(session_handle)`. Ver el detalle de cada uno, con bytes reales, en [referencia-comandos-uci.md](referencia-comandos-uci.md). Internamente usa `uci/` para codificar el comando, lo envía por `transport/`, espera la `Response` correlacionada (mismo `GID`/`OID`, con timeout configurable) y la decodifica.
- Notificaciones: las `Notification` no correlacionadas con el comando en curso no se descartan — se acumulan en `UciClient.notifications` (una lista simple, no una cola con suscripción por ahora) para que quien las necesite (p. ej. la suite de validación) las inspeccione.
- **`UciClient` no tiene ningún hilo de fondo leyendo el transporte**: los bytes solo se leen como efecto colateral de `_send_command_and_wait_response()`. Para observar notificaciones espontáneas durante una ventana de tiempo sin enviar ningún comando (p. ej. mientras dura una sesión de ranging activa), usar `poll_notifications(duration_s)` en un loop — **nunca** `time.sleep()` seguido de leer `notifications`, eso deja los bytes sin leer acumulados en el buffer del sistema operativo (bug real encontrado y corregido en `mixed_ranging.py`, ver [ranging-mixto-cli-uci.md §2.3](ranging-mixto-cli-uci.md#23-mixed_rangingrun_mixed_ranging)).
- `errors.py`: jerarquía `UciError` (`UciTimeoutError`, `UciPayloadError`, `UciStatusError`).
- `models.py`: `dataclasses` de las respuestas/notificaciones parseadas y sus funciones `parse_*`: `DeviceInfo`/`VersionTriplet` (`parse_device_info`), `SessionInitResult` (`parse_session_init_result`), `SessionStatusNotification` (`parse_session_status_notification`), `AppConfigResult`/`RejectedAppConfigParam` (`parse_app_config_response`), `RangingDataNotification` (`parse_ranging_data_notification`, solo decodifica el header de 25 bytes), `TwrMeasurement` (`parse_twr_measurement`, decodifica mac/status/nlos/distancia del primer registro dentro de una medición TWR).

### 3.4 `validation/`

- `spec.py`: definición declarativa de qué comandos ejecutar, con qué parámetros y qué se espera de la respuesta (`Status` esperado, campos del payload).
- `runner.py`: ejecuta la spec contra un `UciClient` ya construido (no abre el puerto ni conoce el transporte concreto), registra resultado por caso.
- `report.py`: genera el reporte (formato a definir en la fase correspondiente del plan de implementación — texto, JSON y/o Markdown).

### 3.5 `app/`

**Pendiente — fase F7, todavía no implementada** (ver [plan-implementacion.md](plan-implementacion.md)). Diseño previsto, sin cambios:

- `cli.py`: comandos Typer (`ports`, `info`, `validate`, ...), construye el transporte y el `UciClient` reales y se los pasa a `validation/`.
- `config.py`, `logging_setup.py`: configuración de la aplicación y logging (incluye el log crudo de tráfico serie en hex, ver [../CLAUDE.md §2.2](../CLAUDE.md#22-estilo-y-calidad)).

## 4. Estrategia de testing sin hardware

- Las capturas reales de hardware (en hex) viven **como constantes a nivel de módulo dentro de cada archivo de test** (p. ej. `REAL_RESET_TX`/`REAL_RESET_RX` en `tests/test_core_client.py`), no en una carpeta `tests/fixtures/` separada — es una diferencia deliberada respecto al diseño original de este documento, más simple para el tamaño actual del proyecto (unas pocas decenas de tramas). Si el volumen de fixtures crece mucho, migrar a archivos separados queda como mejora futura.
- `FakeTransport` (en `tests/fakes.py`, análogo al de `i-mop-qorvo-CLI-script`) reproduce esas tramas byte a byte ante cada `write()`, permitiendo testear `uci/`, `core/` y `validation/` sin abrir un puerto serie real. Soporta además un modo de secuencia (parámetro `responses`, una lista de capturas que se liberan una por una después de cada `write()`) para simular una conversación de varios comandos consecutivos con el timing correcto.
- Los tests que sí requieren hardware real se marcan `@pytest.mark.hardware` y quedan excluidos de la corrida por defecto — en la práctica, hasta ahora toda la validación contra hardware real de este proyecto se hizo con scripts manuales puntuales (no tests automatizados marcados `hardware`), y sus resultados se archivaron en `docs/resultados-validacion.md`/`docs/validaciones/`.

## 5. Puntos de extensión previstos (fuera del alcance inicial)

- **Extensiones propietarias de Qorvo** (`GID` de calibración/test fuera del rango FiRa estándar, ver [protocolo-uci.md §6](protocolo-uci.md#6-extensiones-propietarias-de-qorvo)): si se decide cubrirlas, deberían vivir en un submódulo separado dentro de `uci/`/`core/` (p. ej. `uci/qorvo_ext.py`), nunca mezcladas con la tabla de comandos estándar FiRa.
- **Transporte BLE para UCI real**: si en el futuro un dispositivo remoto habla UCI de verdad sobre BLE, debería entrar como una implementación adicional de la interfaz de `transport/`, sin tocar capas superiores. El puente `hardware/ble-bridge-nrf52840` del proyecto CLI hermano **no sirve para esto**: reenvía comandos CLI de texto sobre Nordic UART Service, no el framing binario UCI.
- **`cli_bridge/` (ranging mixto UCI+CLI, ya implementado):** en vez de portar UCI sobre BLE, se resolvió el caso de uso real (probar ranging con la placa CLI del proyecto hermano) con un subsistema aparte que habla el protocolo nativo de ese puente (shell de Zephyr sobre NUS) y orquesta ambos lados desde `mixed_ranging.py`. Ver [docs/ranging-mixto-cli-uci.md](ranging-mixto-cli-uci.md) para la arquitectura y el resultado real contra hardware.
