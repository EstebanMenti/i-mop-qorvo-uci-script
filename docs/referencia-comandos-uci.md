# Referencia de comandos UCI probados

> **Propósito:** documentar, comando por comando, qué hace cada uno de los comandos UCI implementados en `core/client.py`, qué se envía y qué responde el firmware (con bytes reales capturados contra hardware), y qué significa cada parámetro.
> **Alcance:** solo los comandos ya implementados y probados contra una placa DWM3001CDK real (`QM33SDK-1.1.1`, firmware `*-UCI-FreeRTOS.hex`). Para el framing general (`MT`/`PBF`/`GID`/`OID`) y las tablas completas de `Status`/`GID`/`OID`, ver [protocolo-uci.md](protocolo-uci.md) — este documento no repite esas tablas, se enfoca en el comportamiento de cada comando en uso real.
> **Fuente de los ejemplos:** todos los bytes de este documento son capturas reales (no inventadas), tomadas de `tests/test_core_client.py` y verificadas contra una placa conectada por USB (COM29). Todas corresponden a la misma sesión de prueba salvo que se indique lo contrario.

---

## 1. Cómo leer los ejemplos

Cada trama se muestra en hexadecimal, un byte por grupo. El encabezado de 4 bytes se separa del payload con `|`:

```
20 00 00 01 | 00
└─────────┘   └┘
  header      payload
```

Byte 0 del header combina `MT` (tipo de mensaje), `PBF` (fragmentación) y `GID` (grupo de comando); byte 1 es `OID` (opcode); bytes 2-3 son RFU/longitud. Ver el desglose completo en [protocolo-uci.md §1](protocolo-uci.md#1-framing-de-un-paquete-uci).

Todos los comandos de este documento se probaron con la placa en estado limpio (después de `CORE_RESET`), `session_id`/`session_handle = 1` salvo que se indique otro valor.

---

## 2. Grupo `Core`

### 2.1 `CORE_RESET` — `client.reset()`

**Qué hace:** reinicia el stack UCI del dispositivo. Es el primer comando que conviene enviar al empezar cualquier sesión de trabajo: deja al dispositivo en un estado conocido y, confirmado contra hardware real, **limpia cualquier sesión UWB que hubiera quedado activa** de una corrida anterior (ver la notificación `SESSION_STATUS_NTF` en el ejemplo de abajo).

**Parámetros:** ninguno expuesto por `client.reset()`. El comando UCI en sí toma 1 parámetro fijo, `reset_config` (siempre `0x00` = reinicio del UWBS — no hay otro valor documentado en uso). **Importante:** un payload vacío (sin el byte `0x00`) es inválido — el firmware responde `Status.SYNTAX_ERROR`, confirmado contra hardware real.

**Ejemplo real:**

```
TX: 20 00 00 01 | 00
    (Command, GID=Core, OID=Reset, payload = reset_config=0x00)

RX: 60 01 00 01 | 01                      ← Notification CORE_DEVICE_STATUS_NTF: DeviceState.READY
    40 00 00 01 | 00                      ← Response: Status.OK
    60 01 00 01 | 01                      ← Notification CORE_DEVICE_STATUS_NTF: DeviceState.READY (de nuevo)
```

**Devuelve:** `Status` (se espera `Status.OK`).

**Notas:**
- Las dos notificaciones `CORE_DEVICE_STATUS_NTF` (antes y después de la `Response`) son normales — `UciClient` las captura en `client.notifications`, no las descarta.
- No confundir con `RESTORE` de la CLI de texto: este `RESET` no toca configuración persistente/NVM, solo reinicia el estado en RAM del stack.

### 2.2 `CORE_GET_DEVICE_INFO` — `client.get_device_info()`

**Qué hace:** consulta la identidad del dispositivo — versión del stack FiRa (`UCI`, `MAC`, `PHY`) y datos específicos de fabricante. Útil como primer chequeo de "¿el dispositivo está vivo y habla UCI?" antes de cualquier otra cosa.

**Parámetros:** ninguno (payload vacío).

**Ejemplo real:**

```
TX: 20 02 00 00
    (Command, GID=Core, OID=GetDeviceInfo, sin payload)

RX: 40 02 00 3e | 00 02 00 02 00 02 00 01 10 34 01 01 00 ... (62 bytes)
    (Response, Status=OK, seguido de las versiones y datos de vendor)
```

**Campos de la respuesta** (`DeviceInfo`, ver `core/models.py::parse_device_info`):

| Campo | Bytes del payload | Significado | Valor real observado |
|---|---|---|---|
| `status` | 0 | `Status` de la operación | `OK` |
| `uci_version` | 1-2 | Versión del protocolo UCI (major, minor\|maintenance en nibbles) | `2.0.0` |
| `mac_version` | 3-4 | Versión de la capa MAC de FiRa | `2.0.0` |
| `phy_version` | 5-6 | Versión de la capa PHY de FiRa | `2.0.0` |
| `uci_test_version` | 7-8 | Versión de las extensiones de test UCI | `1.1.0` |
| `vendor_data` | 9 en adelante | Datos específicos de Qorvo — **no decodificados** (fuera de alcance, ver [protocolo-uci.md §6](protocolo-uci.md#6-extensiones-propietarias-de-qorvo)) | 53 bytes crudos |

### 2.3 `CORE_GET_CAPS` — `client.get_caps_raw()`

**Qué hace:** consulta la lista de capacidades del dispositivo (qué modos, canales, tamaños de trama, etc. soporta). Es una lista de longitud variable (formato TLV): tag (1 byte) + longitud (1 byte) + valor.

**Parámetros:** ninguno (payload vacío).

**Ejemplo real:**

```
TX: 20 03 00 00

RX: 40 03 00 5e | 00 1a 00 02 03 01 01 02 ff 00 02 04 02 00 02 00 ... (94 bytes)
    (Response, Status=OK, seguido de la lista TLV de capacidades)
```

**Devuelve:** `(Status, bytes)` — el `Status` (1 byte) y el resto del payload **sin decodificar** (93 bytes en el ejemplo real). Decodificar esta lista tag por tag queda pendiente (no forma parte del alcance actual, ver `docs/plan-implementacion.md` F3); por ahora sirve para confirmar que el comando funciona y archivar la lista cruda.

---

## 3. Grupo `Session`

> **Antes de leer esta sección:** el `session_handle` que devuelve `SESSION_INIT` puede ser **distinto** del `session_id` que el host propuso. Todos los comandos de este grupo (salvo `SESSION_INIT` mismo) toman `session_handle`, no `session_id`. Ver advertencia completa en [protocolo-uci.md §2.1](protocolo-uci.md#21-formato-de-payload-confirmado-comandos-ya-implementados).

### 3.1 `SESSION_INIT` — `client.session_init(session_id, session_type)`

**Qué hace:** crea una sesión UWB. Es el primer paso obligatorio antes de poder rangear: sin una sesión inicializada, `RANGING_START` falla.

**Parámetros:**

| Parámetro | Tamaño | Significado |
|---|---|---|
| `session_id` | 4 bytes LE | Identificador que el host propone para la sesión. El firmware puede asignar un `session_handle` distinto — ver advertencia arriba. |
| `session_type` | 1 byte | Tipo de sesión (`SessionType`): `RANGING` (0x00) es el único probado en este proyecto. Otros valores (`RANGING_AND_DATA`, `DATA`, ...) están definidos pero no probados. |

**Ejemplo real** (pidiendo `session_id=7`):

```
TX: 21 00 00 05 | 07 00 00 00 00
    (session_id=7 LE, session_type=0x00=RANGING)

RX: 41 00 00 05 | 00 01 00 00 00           ← Response: Status=OK, session_handle=1 (¡no 7!)
    61 02 00 06 | 01 00 00 00 00 00        ← Notification SESSION_STATUS_NTF: session=1, state=INIT(0), reason=0
```

**Devuelve:** `SessionInitResult(status, session_handle)`.

### 3.2 `SESSION_SET_APP_CONFIG` — `client.session_set_app_config(...)`

**Qué hace:** configura los parámetros de la sesión antes de poder rangear. **Es un prerrequisito real, no opcional** — confirmado contra hardware real: sin este comando (o con un subconjunto insuficiente de parámetros), `RANGING_START` devuelve `Status.ERROR_SESSION_NOT_CONFIGURED`.

A diferencia de los demás comandos de este documento, el payload usa una codificación genérica **TVS** (Tag-Value-Size): `count` (1 byte) + por cada parámetro, `tag` (1) + `longitud` (1) + `valor`. Implementado en `uci/app_config.py::encode_app_config`.

**Parámetros que acepta `session_set_app_config()`** (15 en total — subconjunto elegido de los ~90 que define el SDK, ver [protocolo-uci.md §2.2](protocolo-uci.md#22-session_set_app_config-bloque-tvs-y-máquina-de-estados-confirmada) para la tabla completa con tags):

| Parámetro Python | Para qué sirve | Valor de ejemplo |
|---|---|---|
| `device_type` | Rol FiRa del dispositivo: `CONTROLLER` (dirige la sesión) o `CONTROLEE` (participa). | `CONTROLLER` |
| `device_role` | Rol de ranging: `INITIATOR` (inicia el intercambio de mensajes) o `RESPONDER` (contesta). | `INITIATOR` |
| `device_mac_address` | Dirección MAC corta (2 bytes) de **este** dispositivo dentro de la sesión. | `0x0000` |
| `dst_mac_addresses` | Lista de direcciones MAC cortas de los dispositivos con los que se quiere rangear (el/los `Controlee`/`Responder`). | `[0x0001]` |
| `multi_node_mode` | Topología de la sesión: `UNICAST` (1 a 1, el único probado), `ONE_TO_MANY`, `MANY_TO_MANY`. | `UNICAST` (default) |
| `ranging_round_usage` | Método de ranging: `DS_TWR_DEFERRED` (Double-Sided Two-Way Ranging diferido, el más común y el usado en las pruebas) u otras variantes (`SS_TWR`, `DS_TWR`, ...). | `DS_TWR_DEFERRED` (default) |
| `channel_number` | Canal UWB (banda de radio) que van a usar ambos dispositivos — **deben coincidir** en los dos extremos. | `9` (default) |
| `sts_config` | Modo de la señal STS (Scrambled Timestamp Sequence, usada para medir tiempo de vuelo con seguridad): `0`=estática (sin necesidad de una clave provisionada). | `0` (default) |
| `rframe_config` | Formato de la trama de radio física usada para el ranging. | `3` (default) |
| `schedule_mode` | Modo de planificación de las rondas de ranging: `1`="por tiempo" (time-based). | `1` (default) |
| `preamble_code_index` | Código de preámbulo UWB — debe coincidir entre los dos dispositivos para que se "escuchen". | `10` (default) |
| `sfd_id` | Identificador de la secuencia SFD (Start-of-Frame Delimiter) de la trama física. | `2` (default) |
| `slot_duration_us` | Duración de cada "slot" de tiempo dentro de una ronda de ranging (unidades RSTU). | `2400` (default) |
| `ranging_interval_ms` | Cada cuánto se repite una ronda de ranging completa, en milisegundos. | `200` (default) |
| `slots_per_rr` | Cantidad de slots por ronda de ranging. | `25` (default) |

Los parámetros marcados "(default)" tienen un valor por defecto razonable en `session_set_app_config()` (los mismos que usa `run_fira_twr.py` del SDK) — normalmente solo hace falta pasar explícitamente `device_type`, `device_role`, `device_mac_address` y `dst_mac_addresses`, que dependen de qué dispositivo es cada placa.

**Ejemplo real:**

```
TX: 21 03 00 38 | 01 00 00 00 0f 00 01 01 11 01 01 03 01 00 01 01 02 06 02 00 00
                  07 02 01 00 04 01 09 02 01 00 12 01 03 22 01 01 14 01 0a 15 01 02
                  08 02 60 09 09 04 c8 00 00 00 1b 01 19
    session_handle=1, luego el bloque TVS: count=0x0f (15 parametros), y cada uno
    como tag,longitud,valor (p. ej. "00 01 01" = tag DEVICE_TYPE, longitud 1, valor 1=CONTROLLER).

RX: 41 03 00 02 | 00 00                     ← Response: Status=OK (el 0x00 extra es
                                               count=0 rechazados; el firmware lo manda
                                               igual aunque no haya rechazos)
    61 02 00 06 | 01 00 00 00 03 00         ← Notification SESSION_STATUS_NTF:
                                               session=1, state=IDLE(3) — la sesión
                                               pasó de INIT a IDLE ("lista para rangear")
```

**Devuelve:** `AppConfigResult(status, rejected)`. Si algún parámetro es inválido, `rejected` trae, por cada uno, su tag y el `Status` puntual del rechazo (no se probó este caso contra hardware real).

**Hallazgo importante:** el SDK de Qorvo (`run_fira_twr.py`) etiqueta solo `device_type`, `device_role`, `multi_node_mode`, `ranging_round_usage`, `device_mac_address` como *"mandatory/minimal"*. **Eso no alcanza en la práctica** — se confirmó contra hardware real que con solo esos 5 (+ `dst_mac_addresses`/`channel_number`), el firmware acepta cada parámetro pero `RANGING_START` sigue fallando con `ERROR_SESSION_NOT_CONFIGURED`. Hacen falta los otros 9 (`sts_config` en adelante) para que el gate de "sesión configurada" se levante.

### 3.3 `SESSION_GET_STATE` — `client.get_session_state(session_handle)`

**Qué hace:** consulta en qué estado está una sesión — útil para verificar una transición antes de seguir con el siguiente paso, en vez de asumirla.

**Parámetros:** `session_handle` (4 bytes LE) — el devuelto por `SESSION_INIT`.

**Ejemplo real** (sesión recién creada, todavía sin configurar):

```
TX: 21 06 00 04 | 01 00 00 00

RX: 41 06 00 02 | 00 00
    (Status=OK, SessionState=0=INIT)
```

**Devuelve:** `(Status, int)` — el segundo valor es el `SessionState` crudo (no se convierte a enum automáticamente, para tolerar un valor inesperado sin romper — usar `SessionState(valor)` si se necesita el nombre simbólico). Estados observados en este proyecto: `INIT`(0) tras `SESSION_INIT`, `IDLE`(3) tras `SESSION_SET_APP_CONFIG` exitoso, `ACTIVE`(2) durante `RANGING_START`, de vuelta a `IDLE`(3) tras `RANGING_STOP`.

### 3.4 `SESSION_GET_COUNT` — `client.get_session_count()`

**Qué hace:** cuenta cuántas sesiones existen actualmente en el dispositivo (0 si no hay ninguna activa). Útil para verificar que `SESSION_INIT`/`SESSION_DEINIT` tuvieron el efecto esperado.

**Parámetros:** ninguno.

**Ejemplo real** (con una sesión activa, y luego sin ninguna):

```
TX: 21 05 00 00

RX (con sesión activa):  41 05 00 02 | 00 01   (Status=OK, count=1)
RX (sin sesiones):       41 05 00 02 | 00 00   (Status=OK, count=0)
```

**Devuelve:** `(Status, int)`.

### 3.5 `SESSION_DEINIT` — `client.session_deinit(session_handle)`

**Qué hace:** elimina una sesión, liberando sus recursos. Buena práctica: llamarlo siempre al terminar de trabajar con una sesión, incluso si algo falló antes.

**Parámetros:** `session_handle` (4 bytes LE).

**Ejemplo real:**

```
TX: 21 01 00 04 | 01 00 00 00

RX: 41 01 00 01 | 00                        ← Response: Status=OK
    61 02 00 06 | 01 00 00 00 01 00         ← Notification SESSION_STATUS_NTF:
                                               session=1, state=DEINIT(1)
```

**Devuelve:** `Status`.

---

## 4. Grupo `Ranging`

> Todos los comandos de este grupo requieren una sesión ya creada (`SESSION_INIT`) **y configurada** (`SESSION_SET_APP_CONFIG`) — ver advertencia en [§3.2](#32-session_set_app_config--clientsession_set_app_config).

### 4.1 `RANGING_START` — `client.ranging_start(session_handle)`

**Qué hace:** inicia las rondas de ranging de la sesión. Con la sesión bien configurada, el dispositivo empieza a ejecutar rondas periódicas (cada `ranging_interval_ms`) y emite una notificación `RANGING_DATA_NTF` por cada una — **incluso si no hay ningún otro dispositivo respondiendo**.

**Parámetros:** `session_handle` (4 bytes LE).

**Ejemplo real — sesión SIN configurar** (resultado esperado, no un bug):

```
TX: 22 00 00 04 | 01 00 00 00

RX: 42 00 00 01 | 15
    (Status=0x15=ERROR_SESSION_NOT_CONFIGURED)
```

**Ejemplo real — sesión configurada** (ver §3.2):

```
TX: 22 00 00 04 | 01 00 00 00

RX: 42 00 00 01 | 00                        ← Response: Status=OK
    60 01 00 01 | 02                        ← Notification CORE_DEVICE_STATUS_NTF: ACTIVE(2)
    61 02 00 06 | 01 00 00 00 02 00         ← Notification SESSION_STATUS_NTF: session=1, state=ACTIVE(2)
    62 00 00 38 | 00 00 00 00 01 00 00 00 00 c8 00 00 00 01 00 ... (56 bytes)
                                             ← Notification RANGING_DATA_NTF, ronda 0
    62 00 00 38 | 01 00 00 00 01 00 00 00 00 c8 00 00 00 01 00 ... (56 bytes)
                                             ← Notification RANGING_DATA_NTF, ronda 1
    (... una más por cada ronda transcurrida mientras se mantiene el socket abierto)
```

**Devuelve:** `Status`.

**`RANGING_DATA_NTF` — header decodificado** (`RangingDataNotification`, ver `core/models.py::parse_ranging_data_notification` y [protocolo-uci.md §3](protocolo-uci.md#3-notificaciones-a-manejar-de-forma-asíncrona) para la tabla completa de bytes):

| Campo | Significado | Valor real observado |
|---|---|---|
| `sequence_number` | Contador de ronda, empieza en 0 y se incrementa en cada `RANGING_DATA_NTF` | `0`, `1`, `2`, ... |
| `session_handle` | La sesión que generó esta ronda | `1` |
| `ranging_interval_ms` | Coincide con el `ranging_interval_ms` configurado | `200` |
| `measurement_type` | Tipo de medición (`RangingMeasType.TWR` confirmado) | `TWR` |
| `n_measurements` | Cantidad de mediciones que trae esta notificación | `1` (aunque no haya otro dispositivo respondiendo) |
| `measurements_raw` | Los datos de la(s) medición(es) — **no decodificados todavía** (el formato depende de `measurement_type`) | bytes crudos |

**Nota importante:** `n_measurements=1` incluso sin un segundo dispositivo real indica que el firmware genera una entrada de medición por cada intento de ronda, probablemente con un código de resultado de "sin respuesta"/timeout dentro de `measurements_raw`. Como esa parte no está decodificada, no se puede confirmar la distancia — eso queda pendiente para cuando haya dos placas.

### 4.2 `RANGING_STOP` — `client.ranging_stop(session_handle)`

**Qué hace:** detiene las rondas de ranging de una sesión activa. La sesión vuelve al estado `IDLE` (lista para un nuevo `RANGING_START`, o para `SESSION_DEINIT`).

**Parámetros:** `session_handle` (4 bytes LE).

**Ejemplo real** (sesión que estaba rangeando):

```
TX: 22 01 00 04 | 01 00 00 00

RX: 42 01 00 01 | 00                        ← Response: Status=OK
    61 02 00 06 | 01 00 00 00 03 00         ← Notification SESSION_STATUS_NTF: session=1, state=IDLE(3)
    60 01 00 01 | 01                        ← Notification CORE_DEVICE_STATUS_NTF: READY(1)
```

**Devuelve:** `Status`.

### 4.3 `RANGING_GET_COUNT` — `client.get_ranging_count(session_handle)`

**Qué hace:** cuenta cuántas rondas de ranging se ejecutaron en la sesión hasta el momento.

**Parámetros:** `session_handle` (4 bytes LE).

**Ejemplo real** (antes de iniciar el ranging):

```
TX: 22 03 00 04 | 01 00 00 00

RX: 42 03 00 05 | 00 00 00 00 00
    (Status=OK, count=0 — 4 bytes LE)
```

**Devuelve:** `(Status, int | None)` — el conteo (4 bytes LE) solo viene presente si `Status == OK`; si no, `get_ranging_count()` devuelve `None` en vez de intentar leer bytes que no están.

---

## 5. Máquina de estados de sesión, confirmada de punta a punta

Resumen de las transiciones de `SessionState` observadas contra hardware real a lo largo de este documento:

```
SESSION_INIT           SESSION_SET_APP_CONFIG      RANGING_START      RANGING_STOP      SESSION_DEINIT
     │                         │                        │                  │                  │
     ▼                         ▼                        ▼                  ▼                  ▼
   INIT (0)  ──────────►    IDLE (3)  ──────────►   ACTIVE (2)  ───────► IDLE (3)  ───────►  DEINIT (1)
```

Cada flecha se confirmó de dos formas independientes: leyendo `SESSION_GET_STATE` después del comando, y observando la `SESSION_STATUS_NTF` que el firmware emite en cada transición (ver ejemplos de cada comando arriba).
