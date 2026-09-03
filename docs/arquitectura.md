# Arquitectura del software

> **Propósito:** definir el diseño de capas del paquete `dwm3001c_uci`, las responsabilidades de cada módulo y las reglas de dependencia entre ellos.
> **Alcance:** diseño previo a la implementación (ver estado del proyecto en [../README.md](../README.md)). Sirve de referencia obligatoria durante la implementación descripta en [plan-implementacion.md](plan-implementacion.md).

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

- `enums.py`: `MessageType` (Command/Response/Notification/Data), `Gid`, `OidCore`, `OidSession`, `OidRanging`, `OidTest`, `Status` — ver tablas completas en [protocolo-uci.md](protocolo-uci.md).
- `framing.py`: codificación de un mensaje lógico (`MT`, `PBF`, `GID`, `OID`, payload) a bytes de trama(s), y el camino inverso: reensamblado de tramas fragmentadas (`PBF`) en un mensaje lógico completo antes de exponerlo.
- `codec.py`: (de)serialización de los payloads TLV/estructurados de cada comando conocido (p. ej. `GET_DEVICE_INFO` response, `SESSION_STATUS_NTF`).
- Módulo puro: sin sockets, sin puertos serie, sin logging de I/O. Recibe y devuelve bytes/objetos de datos (`dataclass`).

### 3.3 `core/`

- `client.py`: `UciClient` — API de alto nivel (`reset()`, `get_device_info()`, `get_caps()`, `session_init(session_id, session_type)`, `ranging_start(session_id)`, ...). Internamente usa `uci/` para codificar el comando, lo envía por `transport/`, espera la `Response` correlacionada (mismo `GID`/`OID`, con timeout configurable) y la decodifica.
- Cola/callback de **notificaciones**: las `Notification` no correlacionadas con un comando en curso se despachan a quien se suscriba (p. ej. la suite de validación esperando un `SESSION_STATUS_NTF` concreto).
- `errors.py`: jerarquía `UciError` (`UciTimeoutError`, `UciStatusError`, `UciFramingError`).
- `models.py`: `dataclasses` de las respuestas/notificaciones parseadas (`DeviceInfo`, `Capabilities`, `SessionStatus`, `RangingData`, ...).

### 3.4 `validation/`

- `spec.py`: definición declarativa de qué comandos ejecutar, con qué parámetros y qué se espera de la respuesta (`Status` esperado, campos del payload).
- `runner.py`: ejecuta la spec contra un `UciClient` ya construido (no abre el puerto ni conoce el transporte concreto), registra resultado por caso.
- `report.py`: genera el reporte (formato a definir en la fase correspondiente del plan de implementación — texto, JSON y/o Markdown).

### 3.5 `app/`

- `cli.py`: comandos Typer (`ports`, `info`, `validate`, ...), construye el transporte y el `UciClient` reales y se los pasa a `validation/`.
- `config.py`, `logging_setup.py`: configuración de la aplicación y logging (incluye el log crudo de tráfico serie en hex, ver [../CLAUDE.md §2.2](../CLAUDE.md#22-estilo-y-calidad)).

## 4. Estrategia de testing sin hardware

- `tests/fixtures/` contiene tramas UCI reales capturadas de una placa (en hex o como bytes), no texto sintético inventado.
- `FakeTransport` (en `tests/fakes.py`, análogo al de `i-mop-qorvo-CLI-script`) reproduce esas tramas byte a byte ante cada `write()`, permitiendo testear `uci/`, `core/` y `validation/` sin abrir un puerto serie real.
- Los tests que sí requieren hardware real se marcan `@pytest.mark.hardware` y quedan excluidos de la corrida por defecto.

## 5. Puntos de extensión previstos (fuera del alcance inicial)

- **Extensiones propietarias de Qorvo** (`GID` de calibración/test fuera del rango FiRa estándar, ver [protocolo-uci.md §6](protocolo-uci.md#6-extensiones-propietarias-de-qorvo)): si se decide cubrirlas, deberían vivir en un submódulo separado dentro de `uci/`/`core/` (p. ej. `uci/qorvo_ext.py`), nunca mezcladas con la tabla de comandos estándar FiRa.
- **Transporte BLE**: si en el futuro se replica el patrón de puente Bluetooth de la rama `hardware/ble-bridge-nrf52840` del proyecto CLI hermano, debería entrar como una implementación adicional de la interfaz de `transport/`, sin tocar capas superiores.
