# Protocolo UCI — resumen relevado del SDK

> **Propósito:** resumir el protocolo UCI (framing, grupos de comando y códigos de estado) para uso como referencia rápida durante el desarrollo, con cita de la fuente.
> **Alcance:** protocolo de aplicación entre el host (esta herramienta) y el firmware `*-UCI-FreeRTOS.hex` de `QM33SDK-1.1.1`. No cubre el protocolo radio UWB en sí (eso es responsabilidad del firmware/driver DW3xxx).
>
> **Fuentes:**
> - Especificación oficial: `SDK/Documentation/uwb-stack/uwb-uci-messages-api-*.pdf` y `uwb-fira-protocol-*.pdf` (release `QM33SDK-1.1.1`, en el repositorio `i-mop-qorvo-uci-fw`). **No se transcriben aquí en detalle** — son la fuente de verdad ante cualquier discrepancia.
> - Implementación Python de referencia de Qorvo: `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/*.py` (mismo release). Usada únicamente para **confirmar y extraer** los valores de las tablas de abajo (framing, `Gid`, `OidCore`/`OidSession`/`OidRanging`/`OidTest`, `Status`) — **no reutilizar ese código fuente**, ver nota legal en [§7](#7-nota-legal-sobre-el-código-fuente-de-referencia).
>
> Todo lo que no está explícitamente respaldado por una de estas dos fuentes se marca **`[Sin confirmar]`**.

---

## 1. Framing de un paquete UCI

Formato del encabezado (4 bytes) más payload:

```
Byte 0:  MT (3 bits) << 5 | PBF (1 bit) << 4 | GID (4 bits)
Byte 1:  OID (1 byte)
Byte 2:  RFU (0x00)
Byte 3:  longitud del payload (1 byte)
          — excepción: en un Data Packet (MT=0), los bytes 2-3 forman
            la longitud como entero de 16 bits little-endian.
Bytes 4..: payload
```

| Campo | Tamaño | Descripción |
|---|---|---|
| `MT` (Message Type) | 3 bits | `0` = Data Packet, `1` = Command, `2` = Response, `3` = Notification |
| `PBF` (Packet Boundary Flag) | 1 bit | `0` = Final (mensaje completo en este paquete), `1` = hay más paquetes de este mismo mensaje a continuación |
| `GID` (Group ID) | 4 bits | Grupo de comando — ver [§2](#2-grupos-de-comando-gid-y-opcodes-oid) |
| `OID` (Opcode ID) | 1 byte | Comando dentro del grupo |

> **Nota — reensamblado:** cuando `PBF = 1`, el mensaje lógico continúa en el/los paquete(s) siguiente(s) con el mismo `GID`/`OID`; el consumidor debe reensamblar antes de decodificar el payload. El tamaño máximo de payload por paquete para `MT != Data Packet` es **255 bytes** — se deriva directamente de que el campo de longitud (byte 3) es de 1 byte, no es un valor arbitrario de implementación. Implementado en `src/dwm3001c_uci/uci/framing.py` (`MAX_PAYLOAD_SIZE`).
>
> **Nota — valores de `MT` adicionales, fuera de alcance actual:** al leer `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/addin_transport_uart.py` (parser de framing del lado host, funciones `check_data`/`data_received`) se confirmó que el campo `MT` de 3 bits admite, ademas de los 4 valores documentados arriba, los valores `0b100` y `0b101` ("Control message format for testing"), que **usan longitud de 16 bits** (bytes 2-3, little-endian) igual que un Data Packet, no el byte de longitud de 1 byte de un Command/Response/Notification normal. No se conoce el nombre oficial de estos dos tipos ni su relación exacta con el grupo `Test` (`GID=0x0D`) — **`[Sin confirmar]`**. El codec de `src/dwm3001c_uci/uci/framing.py` todavía **no los soporta** (el `MessageType` enum solo define 0-3); esto es aceptable mientras el grupo `Test` no esté en el alcance de implementación (no forma parte de ninguna fase de [plan-implementacion.md](plan-implementacion.md)), pero debe resolverse antes de implementar `OidTest`.
>
> El mismo archivo también revela una técnica de sincronización usada por la herramienta de Qorvo al abrir un puerto que puede tener bytes a medio recibir: descarta bytes iniciales hasta encontrar un nibble superior de byte 0 en `{4, 5, 6, 7}` (inicio válido de Response/Notification). El cliente UCI de este proyecto (`core/`, fase F3) debería considerar una estrategia equivalente al abrir el puerto por primera vez, en vez de asumir que el primer byte leído es el inicio de una trama.

## 2. Grupos de comando (GID) y opcodes (OID)

| GID | Nombre | OID principales relevados |
|---|---|---|
| `0x00` | `Core` | `RESET` (`0x00`), `DEVICE_STATUS_NTF` (`0x01`, notificación), `GET_DEVICE_INFO` (`0x02`), `GET_CAPS` (`0x03`), `SET_CONFIG` (`0x04`), `GET_CONFIG` (`0x05`), `GENERIC_ERROR_NTF` (`0x07`, notificación), `GET_TIME` (`0x08`) |
| `0x01` | `Session` | `INIT` (`0x00`), `DEINIT` (`0x01`), `STATUS_NTF` (`0x02`, notificación), `SET_APP_CONFIG` (`0x03`), `GET_APP_CONFIG` (`0x04`), `GET_COUNT` (`0x05`), `GET_STATE` (`0x06`), `UPDATE_MULTICAST_LIST` (`0x07`), `SET_ANCHOR_RANGING_ROUNDS` (`0x08`), `SET_TAG_ACTIVITY` (`0x09`), `GET_DATA_SIZE` (`0x0B`), `UPDATE_HUS` (`0x0C`) |
| `0x02` | `Ranging` | `START` (`0x00`), `STOP` (`0x01`), `GET_COUNT` (`0x03`), `DATA_CREDIT` (`0x04`), `DATA_TRANSFER_STATUS` (`0x05`) |
| `0x0D` | `Test` | `CONFIG_SET` (`0x00`), `CONFIG_GET` (`0x01`), `PERIODIC_TX` (`0x02`), `PER_RX` (`0x03`), `RX` (`0x05`), `LOOPBACK` (`0x06`), `STOP_SESSION` (`0x07`), `SS_TWR` (`0x08`) |
| *(propietario)* | `Qorvo` / `Calibration` | Ver [§6](#6-extensiones-propietarias-de-qorvo). |

> **Nota:** los valores de `GID`/`OID` de esta tabla fueron confirmados por lectura directa de `fira_enums.py` (mismo archivo citado en §4) y coinciden byte a byte con esa fuente. Lo que **no** está confirmado todavía es el formato del *payload* de cada comando — antes de implementar el codec de un comando concreto, confirmar los campos del payload contra `uwb-uci-messages-api-*.pdf`.

### 2.1 Formato de payload confirmado (comandos ya implementados)

Los siguientes formatos de payload están confirmados tanto contra `fira.py`/`fira_msg.py` del SDK como contra una captura real de hardware (placa DWM3001CDK, firmware UCI `QM33SDK-1.1.1`) — implementados en `src/dwm3001c_uci/core/client.py` y `core/models.py`:

| Comando | Payload del Command | Payload de la Response |
|---|---|---|
| `CORE_RESET` | **1 byte**: `0x00` (tipo de reset). Un payload vacío devuelve `Status.SYNTAX_ERROR` — confirmado contra hardware real, no es un valor opcional. | 1 byte: `Status`. |
| `CORE_GET_DEVICE_INFO` | Vacío. | `Status` (1) + `uci_version` (2: major, minor\|maintenance en nibbles) + `mac_version` (2) + `phy_version` (2) + `uci_test_version` (2) + resto: datos específicos de Qorvo sin decodificar (`vendor_data`, ver [§6](#6-extensiones-propietarias-de-qorvo)). |
| `CORE_GET_CAPS` | Vacío. | `Status` (1) + lista TLV de parámetros de capacidad (tag 1 byte, longitud 1 byte, valor). **No se decodifica todavía** — `get_caps_raw()` devuelve `(Status, bytes)` sin parsear la lista (ver `docs/plan-implementacion.md` F3). |
| `SESSION_INIT` | `session_id` (4 bytes LE, elegido por el host) + `session_type` (1 byte, ver `SessionType`). | `Status` (1) + `session_handle` (4 bytes LE). Ver advertencia abajo. |
| `SESSION_DEINIT` | `session_handle` (4 bytes LE). | `Status` (1). |
| `SESSION_GET_STATE` | `session_handle` (4 bytes LE). | `Status` (1) + `SessionState` (1). |
| `SESSION_GET_COUNT` | Vacío. | `Status` (1) + cantidad de sesiones (1). |
| `SESSION_STATUS_NTF` (notificación) | — | `session_id`/`session_handle` (4 bytes LE) + `SessionState` (1) + código de motivo (1, ver `SessionStateChangeReason`). |
| `SESSION_SET_APP_CONFIG` | `session_handle` (4 bytes LE) + bloque TVS (ver tabla y nota abajo). | `Status` (1). Si `Status == OK`, el firmware igual agrega un byte extra (`0x00`, cantidad de rechazados) que la librería de referencia ni siquiera lee — nuestro parser lo tolera sin exigirlo. Si `Status != OK`: + cantidad de parámetros rechazados (1) + por cada uno, tag (1) + `Status` puntual (1). |
| `RANGING_START` | `session_handle` (4 bytes LE). | `Status` (1). Requiere que la sesión ya haya sido configurada con `SESSION_SET_APP_CONFIG` — sin eso, confirmado contra hardware real que devuelve `Status.ERROR_SESSION_NOT_CONFIGURED`. Con la sesión configurada, confirmado que devuelve `Status.OK` y dispara `RANGING_DATA_NTF` en cada ronda (ver tabla de notificaciones). |
| `RANGING_STOP` | `session_handle` (4 bytes LE). | `Status` (1). |
| `RANGING_GET_COUNT` | `session_handle` (4 bytes LE). | `Status` (1) + cantidad de mediciones (4 bytes LE), presente **solo** si `Status == OK`. |

> **Advertencia confirmada contra hardware real — `session_handle` puede diferir de `session_id`:** al pedir `SESSION_INIT` con `session_id=7`, el firmware devolvió `session_handle=1`. Usar despues ese `7` (el id original) en `SESSION_GET_STATE`/`SESSION_DEINIT` devuelve `Status.ERROR_SESSION_NOT_EXIST`; hay que usar el `session_handle` de la Response de `SESSION_INIT`. El cliente Python de referencia de Qorvo (`fira.py`) no hace esta distinción — reutiliza la misma variable `sid` en todos los métodos, asumiendo implícitamente que son iguales — por lo que **no se debe copiar ese supuesto sin verificar**. `src/dwm3001c_uci/core/client.py` ya reflejó esto: `session_deinit()`/`get_session_state()` reciben `session_handle`, no `session_id`.
>
> También se confirmó que `CORE_RESET` limpia sesiones activas colgadas de una corrida anterior, emitiendo `SESSION_STATUS_NTF` (estado `DEINIT`) por cada una.

### 2.2 `SESSION_SET_APP_CONFIG`: bloque TVS y máquina de estados confirmada

`SESSION_SET_APP_CONFIG` usa una codificación genérica Tag-Value-Size, distinta de los payloads fijos de arriba: `count` (1 byte) + por cada parámetro, `tag` (1) + `longitud` (1) + `valor`. Formato confirmado contra `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/core.py` (función `tvs_to_bytes`) y `fira_app.py` (tabla de longitudes `App.defs`, que define ~90 parámetros en total — este proyecto solo implementa la codificación de 15, ver `uci/app_config.py`):

| Parámetro (`AppConfigParam`) | Tag | Longitud | Valor usado por este proyecto |
|---|---|---|---|
| `DEVICE_TYPE` | `0x00` | 1 | `DeviceType.CONTROLLER`/`CONTROLEE` |
| `RANGING_ROUND_USAGE` | `0x01` | 1 | `RangingRoundUsage.DS_TWR_DEFERRED` (default) |
| `STS_CONFIG` | `0x02` | 1 | `0` (Static) |
| `MULTI_NODE_MODE` | `0x03` | 1 | `MultiNodeMode.UNICAST` (default) |
| `CHANNEL_NUMBER` | `0x04` | 1 | `9` (default) |
| `DEVICE_MAC_ADDRESS` | `0x06` | 2 | elegido por el llamador |
| `DST_MAC_ADDRESS` | `0x07` | 2 por elemento (es una lista) | elegido por el llamador |
| `SLOT_DURATION` | `0x08` | 2 | `2400` (default, en unidades RSTU) |
| `RANGING_INTERVAL` | `0x09` | 4 | `200` (default, ms) |
| `DEVICE_ROLE` | `0x11` | 1 | `DeviceRole.INITIATOR`/`RESPONDER` |
| `RFRAME_CONFIG` | `0x12` | 1 | `3` (default, "SP3"/`Qp3` en `fira_enums.py`) |
| `PREAMBLE_CODE_INDEX` | `0x14` | 1 | `10` (default) |
| `SFD_ID` | `0x15` | 1 | `2` (default) |
| `SLOTS_PER_RR` | `0x1B` | 1 | `25` (default) |
| `SCHEDULE_MODE` | `0x22` | 1 | `1` (default, "time") |

> **Hallazgo confirmado contra hardware real:** `run_fira_twr.py` del SDK etiqueta solo los primeros 5 (`DEVICE_TYPE`, `DEVICE_ROLE`, `MULTI_NODE_MODE`, `RANGING_ROUND_USAGE`, `DEVICE_MAC_ADDRESS`) como *"Fira Mandatory/minimal session config"*. **Eso no alcanza en la práctica**: se probó configurar una sesión con solo esos 5 (más `DST_MAC_ADDRESS`/`CHANNEL_NUMBER`) y el firmware acepta cada parámetro individualmente (`Status.OK`, ningún parámetro rechazado), pero `RANGING_START` seguía devolviendo `Status.ERROR_SESSION_NOT_CONFIGURED`. Agregando los 9 parámetros restantes de la tabla (con los mismos valores por defecto que usa `run_fira_twr.py`), `RANGING_START` pasó a devolver `Status.OK` y la sesión arrancó a rangear de verdad.
>
> **Máquina de estados de sesión confirmada de punta a punta contra hardware real:** `SESSION_INIT` → `SessionState.INIT` (0) → `SESSION_SET_APP_CONFIG` exitoso → `SessionState.IDLE` (3) → `RANGING_START` → `SessionState.ACTIVE` (2) → `RANGING_STOP` → `SessionState.IDLE` (3) → `SESSION_DEINIT` → `SessionState.DEINIT` (1). Cada transición se confirmó tanto vía `SESSION_GET_STATE` como vía la `SESSION_STATUS_NTF` correspondiente.
>
> Todo esto se probó con **una sola placa, sin un segundo dispositivo que responda**: el `Controller` corre igual las rondas de ranging configuradas (confirmado: 9 rondas en ~1 segundo con `ranging_interval_ms=200`) y emite `RANGING_DATA_NTF` en cada una, aunque no haya `Controlee` — ver notificación en la sección siguiente. No se validó una medición de distancia real entre dos dispositivos.

## 3. Notificaciones a manejar de forma asíncrona

Al menos las siguientes `Notification` pueden llegar sin estar correlacionadas 1:1 con el último comando enviado, y el cliente debe poder despacharlas por separado (ver [arquitectura.md §3.3](arquitectura.md#33-core)):

- `CORE_DEVICE_STATUS_NTF` (`GID=0x00`, `OID=0x01`)
- `CORE_GENERIC_ERROR_NTF` (`GID=0x00`, `OID=0x07`)
- `SESSION_STATUS_NTF` (`GID=0x01`, `OID=0x02`)
- `RANGING_DATA_NTF` (`GID=0x02`, `OID=0x00` — mismo GID/OID que el comando `RANGING_START`, distinguible por `MT=NOTIFICATION`). **Confirmado contra hardware real** (antes `[Sin confirmar]`): se emite en cada ronda de ranging, incluso sin un segundo dispositivo que responda. Header (25 bytes, formato confirmado contra `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/qorvo_msg.py`, clase `RangingData`) — implementado en `core/models.py::parse_ranging_data_notification`:

  | Campo | Bytes | Descripción |
  |---|---|---|
  | `sequence_number` | 0-3 | Contador de ronda, empieza en 0 |
  | `session_handle` | 4-7 | — |
  | RFU | 8 | — |
  | `ranging_interval_ms` | 9-12 | Coincide con el `RANGING_INTERVAL` configurado |
  | `measurement_type` | 13 | `RangingMeasType` (`TWR`=1 confirmado) |
  | RFU | 14 | — |
  | modo de direccionamiento MAC | 15 | `0`→2 bytes, `1`→8 bytes |
  | `primary_session_id` | 16-19 | `0` si no aplica |
  | RFU | 20-23 | — |
  | `n_measurements` | 24 | Cantidad de mediciones que siguen |

  Las mediciones individuales (bytes 25 en adelante, formato depende de `measurement_type`) **no se decodifican todavía** — quedan crudas en `RangingDataNotification.measurements_raw`. En la CLI de texto del proyecto hermano el equivalente es `SESSION_INFO_NTF`.

## 4. Códigos de estado (`Status`)

Valores confirmados por lectura directa de `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/fira_enums.py` (clase `Status`, release `QM33SDK-1.1.1`) — no son un resumen aproximado, coinciden byte a byte con esa fuente:

| Categoría | Valores confirmados |
|---|---|
| Genéricos (`0x00`–`0x0A`) | `OK` (`0x00`), `REJECTED` (`0x01`), `FAILED` (`0x02`), `SYNTAX_ERROR` (`0x03`), `INVALID_PARAM` (`0x04`), `INVALID_RANGE` (`0x05`), `INVALID_MESSAGE_SIZE` (`0x06`), `UNKNOWN_GID` (`0x07`), `UNKNOWN_OID` (`0x08`), `READ_ONLY` (`0x09`), `COMMAND_RETRY` (`0x0A`) |
| Sesión (`0x11`–`0x1B`) | `ERROR_SESSION_NOT_EXIST` (`0x11`), `ERROR_SESSION_DUPLICATE` (`0x12`), `ERROR_SESSION_ACTIVE` (`0x13`), `ERROR_MAX_SESSIONS_EXCEEDED` (`0x14`), `ERROR_SESSION_NOT_CONFIGURED` (`0x15`), `ERROR_ACTIVE_SESSIONS_ONGOING` (`0x16`), `ERROR_MULTICAST_LIST_FULL` (`0x17`), `ERROR_UWB_INITIALIZATION_TIME_TOO_OLD` (`0x1A`), `RANGING_NEGATIVE_DISTANCE` (`0x1B`) |
| Ranging (`0x20`–`0x2A`) | `RANGING_TX_FAILED` (`0x20`), `RANGING_RX_TIMEOUT` (`0x21`), `RANGING_RX_PHY_DEC_FAILED` (`0x22`), `RANGING_RX_PHY_TOA_FAILED` (`0x23`), `RANGING_RX_PHY_STS_FAILED` (`0x24`), `RANGING_RX_MAC_DEC_FAILED` (`0x25`), `RANGING_RX_MAC_IE_DEC_FAILED` (`0x26`), `RANGING_RX_MAC_IE_MISSING` (`0x27`), `ERROR_ROUND_INDEX_NOT_ACTIVATED` (`0x28`), `ERROR_NUMBER_OF_ACTIVE_ROUND_EXCEEDED` (`0x29`), `ERROR_DL_TDOA_DEVICE_ADDRESS_NOT_MATCHING_IN_REPLY_TIME_LIST` (`0x2A`) |
| Propietario (`0x50`–`0xFF`) | Solo confirmados: `ERROR_SE_BUSY` (`0x50`), `ERROR_CCC_LIFE_CYCLE` (`0x51`), `UNKNOWN` (`0xFF`, usado por la librería de referencia como valor de relleno). El resto del rango no está enumerado — no asumir su significado sin volver a esta fuente. |

Implementado en `src/dwm3001c_uci/uci/enums.py` (`Status`), con `status_name()` como fallback seguro para valores no enumerados (p. ej. si el firmware devuelve un código propietario no listado arriba). Toda respuesta con `Status != OK` debe reportarse en logs y en el reporte de validación con el **nombre simbólico**, no solo el valor numérico (ver [../CLAUDE.md §2.2](../CLAUDE.md#22-estilo-y-calidad)).

## 5. Transporte

- El transporte confirmado para el protocolo UCI en este SDK es **UART** sobre el puerto COM virtual (USB CDC ACM) de la placa. No se relevó soporte de SPI a nivel de framing UCI del host (SPI se usa a nivel del driver del transceptor DW3xxx, capa distinta y fuera de alcance de este proyecto).
- **Baud rate confirmado: 115200.** Fuente: `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/addin_transport_uart.py`, clase `UartTransport.__init__` — `kwargs["baudrate"] = 115200` como valor por defecto de la propia herramienta de Qorvo para hablar UCI. Coincide con el valor que ya usaba el firmware CLI de texto, pero ahora está confirmado para UCI específicamente, no asumido por analogía. Bits/paridad/stop bits no vienen explícitos en ese archivo (pyserial usa 8N1 por defecto, que es lo que configura `SerialLink`); si se observa un problema de framing contra hardware real, revisar esto primero.

## 6. Extensiones propietarias de Qorvo

El SDK define grupos de comando (`GID`) y comandos adicionales fuera del estándar FiRa, para funciones de fábrica/depuración: pruebas de RF (`test_tx_cw`, `test_pll_lock`, `test_tof`, `test_rtc`) y gestión de calibración (`get_cal`/`set_cal`, con claves del estilo `ant<x>.ch<y>.ant_delay`, conceptualmente equivalentes a `CALKEY`/`LISTCAL` de la CLI de texto).

Estas extensiones **quedan fuera del alcance inicial** de este proyecto (ver [../CLAUDE.md §1.1](../CLAUDE.md#11-qué-es)). Si en el futuro se decide cubrirlas, deben documentarse en un anexo separado de este archivo, citando la fuente, y no mezclarse con las tablas de comandos estándar de arriba.

## 7. Nota legal sobre el código fuente de referencia

La librería Python `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/*.py` usada para confirmar las tablas de este documento lleva la cabecera `SPDX-License-Identifier: LicenseRef-QORVO-2` (licencia propietaria de Qorvo). **No está confirmado que esa licencia permita copiar o derivar código hacia este repositorio.** Esta herramienta reimplementa el codec de forma independiente, usando esos archivos únicamente como referencia de lectura para entender y verificar el protocolo. Ver regla explícita en [../CLAUDE.md §2.4](../CLAUDE.md#24-dependencias).
