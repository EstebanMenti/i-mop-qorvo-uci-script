# Ranging mixto: placa UCI (local, USB) + placa CLI (remota, BLE)

> **Propósito:** documentar la herramienta que hace un ranging real entre una placa local con firmware UCI (nuestro `UciClient`, por USB) y una placa remota con firmware CLI de texto, controlada por Bluetooth a través del puente `I-mop-nrf52840-fw`.
> **Alcance:** arquitectura de `cli_bridge/` y `mixed_ranging.py`, cómo usarlos, y el resultado real contra hardware. **Ranging físico real logrado** (sexta corrida, ver §4): el hallazgo faltante era que `RESPF -ID` (lado CLI) debe coincidir con el `session_id` de la sesión UCI (lado local) — no estaba documentado en ninguna fuente oficial de Qorvo relevada hasta ahora, y se confirmó comparando contra un proyecto hermano independiente (`uwb-qorvo-tools`) que ya tenía esta misma mezcla CLI+UCI funcionando.

---

## 1. Por qué existe esto

`docs/plan-implementacion.md` ya documentaba que el banco BLE del proyecto hermano (`i-mop-qorvo-CLI-script`, rama `hardware/ble-bridge-nrf52840`) corre firmware **CLI** de texto, no UCI — así que no sirve "tal cual" como segunda placa UCI. La pregunta de seguimiento fue: ¿pueden interoperar por aire una placa CLI y una UCI, ya que ambas corren el mismo motor FiRa/MAC/PHY por debajo (confirmado contra el Developer Manual del SDK)? Este módulo construye la herramienta para probarlo empíricamente, en vez de quedarse en la teoría.

## 2. Arquitectura

```
src/dwm3001c_uci/
├── cli_bridge/              ← protocolo de texto (shell Zephyr sobre BLE), NO es UCI
│   ├── ble_transport.py     ← BleShellTransport: transporte sincrono sobre NUS (bleak)
│   ├── client.py            ← CliBridgeClient: power_on/off, STAT/STOP/RESPF/INITF
│   └── errors.py            ← BleShellError, BleShellTimeoutError, CliBridgeError
└── mixed_ranging.py         ← orquestador: un UciClient (local) + un CliBridgeClient (remoto)
```

`cli_bridge/` vive deliberadamente **separado** de `transport/`/`uci/`/`core/`: habla un protocolo de texto completamente distinto (el shell de Zephyr del puente nRF52840, documentado en `I-mop-nrf52840-fw/doc/00_BLE_Protocol_Specification.md`), no UCI. Mezclarlo en las mismas capas hubiera confundido dos protocolos con vocabularios de capa parecidos pero significados distintos.

### 2.1 `BleShellTransport`

Transporte sobre **Nordic UART Service (NUS)**, confirmado contra la especificación del bridge (v1.21, sección "`qorvo`: IMPLEMENTADO Y VALIDADO EN HARDWARE REAL"):

- UUIDs de NUS RX/TX confirmados (`6e400002.../6e400003...`).
- Terminador de línea `\n` (el `\r` se ignora).
- El shell **no tiene eco** y **no usa ANSI/VT100** — la señal de "respuesta completa" es que reaparece el prompt del shell (`bt_nus:~$ `), que este transporte detecta con una regex en vez de replicar la ventana de silencio de 400 ms que usa el firmware del bridge internamente (ese detalle es interno al bridge).
- Usa `bleak` (extra opcional `pip install -e .[ble]`) con un hilo dedicado corriendo su propio event loop de asyncio — requisito del backend WinRT de Windows: todas las llamadas de una misma conexión GATT deben venir del mismo hilo/loop. Los métodos públicos son síncronos.

### 2.2 `CliBridgeClient`

Envuelve el comando `qorvo` del bridge:

| Método | Comando real enviado | Para qué sirve |
|---|---|---|
| `power_on(duration=None)` | `qorvo on` / `qorvo on -t <duration>` | Enciende el Qorvo remoto (GPIO). Espera ~1.5 s después (`settle_s`) para que termine de arrancar — **precondición obligatoria** antes de cualquier otro comando. |
| `power_off(duration=None)` | `qorvo off` / `qorvo off -t <duration>` | Apaga el Qorvo remoto. |
| `stat()` | `qorvo STAT` | Estado/versión del Qorvo remoto (JSON). |
| `stop()` | `qorvo STOP` | Detiene la app FiRa activa (`INITF`/`RESPF`/`LISTENER`). |
| `respf(**opts)` | `qorvo RESPF -OPT=valor ...` | Arranca el Qorvo remoto como responder FiRa TWR. |
| `initf(**opts)` | `qorvo INITF -OPT=valor ...` | Arranca el Qorvo remoto como initiator FiRa TWR. |
| `send_qorvo_command(texto)` | `qorvo <texto>` | Pasamanos genérico a cualquier comando de la CLI del Qorvo. |

`send_qorvo_command` levanta `CliBridgeError` si la respuesta empieza con `"Error"` (los mensajes de error documentados del bridge: timeout hacia el Qorvo, puente UART no disponible, etc.) — no los deja pasar como si fueran una respuesta válida de la CLI.

### 2.3 `mixed_ranging.run_mixed_ranging(...)`

Orquesta un ciclo completo:

1. Abre el puerto USB local y hace `CORE_RESET` + `SESSION_INIT` + `SESSION_SET_APP_CONFIG` (Controller/Initiator, dirección `0x0000`) sobre la placa UCI.
2. Conecta por BLE al puente remoto, enciende el Qorvo (`qorvo on`), y lo configura como `RESPF` (Responder, dirección `0x0001`) con los mismos `CHAN`/`PCODE`/`RRU` que el lado UCI.
3. Arranca el ranging local (`RANGING_START`) y durante `duration_s` segundos decodifica cada `RANGING_DATA_NTF` que llega, extrayendo la medición TWR (`core/models.py::parse_twr_measurement`).
4. Al terminar (siempre, incluso si algo falló antes): detiene el ranging, deinicializa la sesión local, detiene la app remota y **apaga el módulo remoto** (`power_off`) — es una placa a batería compartida por una flota (`UWB-Node-1..9`), no conviene dejarla encendida.

**La distancia se mide del lado UCI, no del lado CLI** — confirmado que hace falta: la especificación del bridge documenta explícitamente que `qorvo <comando>` es estrictamente petición/respuesta y **no reenvía notificaciones asíncronas** no solicitadas del Qorvo (`SESSION_INFO_NTF` con la distancia real). En la práctica, si las notificaciones llegan lo bastante seguido (cada `RANGING_DURATION`, por defecto 200 ms, muy por debajo del margen de silencio de 400 ms del bridge), sí quedan capturadas dentro de la ventana de respuesta del comando que las precede (confirmado: ver §4) — pero esto es incidental, no algo en lo que apoyarse: el mecanismo de medición soportado por este proyecto es el lado UCI.

> **Bug real encontrado y corregido durante esta investigación:** la primera versión de este loop usaba `time.sleep(poll_interval_s)` para esperar notificaciones espontáneas. `UciClient` **no tiene ningún hilo de fondo leyendo el puerto serie** — los bytes solo se leen y decodifican como efecto colateral de `_send_command_and_wait_response()` (al esperar la `Response` de un comando activo). Dormir sin enviar nada deja los bytes acumulándose sin leer en el buffer del sistema operativo: solo se veían 2-3 notificaciones por corrida (las que alcanzaban a colarse en la lectura de `ranging_start()`/`ranging_stop()`), nunca las decenas reales que el firmware efectivamente mandaba. Se agregó `UciClient.poll_notifications(duration_s)` (lee y decodifica en loop sin esperar ningún comando específico) y `mixed_ranging.py` ahora lo usa en vez de dormir — confirmado contra hardware real: con el fix, una corrida de 8s pasó de "ver" 3 rondas a ver las 45 reales.

### Uso

```bash
pip install -e ".[ble]"
python -m dwm3001c_uci.mixed_ranging --local-port COM29 --remote-ble-name "UWB-Node-2" --duration-s 8
```

## 3. Parámetros usados para intentar la interoperabilidad

Ambos lados se configuraron con los **mismos valores por defecto** que usa el SDK de Qorvo (`run_fira_twr.py`) y que muestra por defecto el firmware CLI (`INITF`/`RESPF` sin opciones) — confirmado que coinciden byte a byte entre ambas fuentes:

| Parámetro | Valor | Fuente de la confirmación |
|---|---|---|
| Canal (`CHAN`/`CHANNEL_NUMBER`) | 9 | Default de `INITF`/`RESPF` y de `session_set_app_config()` |
| Código de preámbulo (`PCODE`) | 10 | idem |
| Tipo de ranging (`RRU`/`RANGING_ROUND_USAGE`) | DS-TWR deferred | idem |
| `SLOT_DURATION` | 2400 RSTU | idem |
| `RANGING_DURATION`/`ranging_interval_ms` | 200 ms | idem |
| `SLOTS_PER_RR` | 25 | idem |
| `RFRAME_CONFIG` | SP3 (valor `3`) | idem |
| `SFD_ID` | 2 | idem |
| **`VENDOR_ID`** | `0x0708` | Confirmado contra Tabla 7.6 del Developer Manual: la CLI expone `VENDOR_ID`+`STATIC_STS_IV` como un solo valor de 8 bytes (`VUPPER`/`vUpper64`, default `01:02:03:04:05:06:07:08`) — `vendor_id`/`static_sts_iv` son los dos "pedazos" en que UCI la separa |
| **`STATIC_STS_IV`** | `01:02:03:04:05:06` | idem — clave STS estática compartida, necesaria para que dos dispositivos en modo STS estático (`STS_CONFIG=0`) se "escuchen" |
| **`STS_LENGTH`** | `1` (64 símbolos) | Confirmado contra Tabla 7.7 del Developer Manual ("BPRF mode operating parameter sets"): el perfil `PRFSET=BPRF4` (default de la CLI) usa `STS Segment Length = 64` símbolos. Agregado en la segunda iteración — antes no se fijaba en absoluto del lado UCI |
| Direcciones MAC | Local `0x0000` (Controller/Initiator), remota `0x0001` (Controlee/Responder) | Coincide con los defaults de `RESPF` (`ADDR=1, PADDR=0`) |
| **`session_id` / `RESPF -ID`** | El mismo valor en ambos lados | **Imprescindible, no un default compartido:** a diferencia de todo lo anterior, esto no coincide "por default" (el default de la CLI es `ID=42`, el de este cliente era `session_id=1`) — hay que pasarlo explícitamente igual en `session_init()` (UCI) y en `RESPF -ID=` (CLI). No documentado en ninguna fuente oficial de Qorvo relevada; confirmado necesario comparando contra `uwb-qorvo-tools` (ver §4, corrida 6) y validado: sin esto, `RANGING_RX_TIMEOUT` en el 100% de las rondas; con esto, ranging real. |
| `NUMBER_OF_CONTROLEES` | `1` | Presente en la config validada de `uwb-qorvo-tools` (ausente en `run_fira_twr.py`); agregado por paridad al confirmar la causa raíz de arriba, no confirmado como necesario por sí solo |

## 4. Resultado contra hardware real (seis corridas — ranging logrado en la sexta)

**Fecha:** 2026-09-03. **Placas:** local en `COM29` (firmware UCI), remota `UWB-Node-2` (DWM3001CDK detrás de un puente nRF52840, firmware CLI `1.1.0`, build `Aug 10 2026`, `UWB stack: R12.7.0-405-gb33c5c4272`). **Confirmado por el usuario:** ambas placas están físicamente cerca y sin obstáculos.

**✅ Ranging físico real logrado (corrida 6):** `mixed_ranging.py` contra `COM29` + `UWB-Node-2`, dos corridas de 8s consecutivas: **23/45 y 17/45 rondas con `status=OK`**, distancias entre 0cm y 67cm (consistente con placas muy cercanas). El resto de las rondas fallidas en esa misma corrida no fueron timeout sino `RANGING_NEGATIVE_DISTANCE` (0x1B) — un resultado FiRa normal a muy corta distancia (el cálculo de tiempo de vuelo da un valor levemente negativo por ruido de reloj/medición). **Sin calibración de retardo de antena** (fuera de alcance de este proyecto en su fase inicial, ver `CLAUDE.md` §1.1) la distancia medida tiene además un sesgo real, que hace más frecuente este resultado incluso a distancias que no son exactamente cero — no separar más las placas para "arreglarlo": sin calibrar, el sesgo sigue estando ahí a cualquier distancia. No es un síntoma de mala configuración del protocolo.

**Causa raíz encontrada:** el `session_id` de la sesión UCI local (pasado a `session_init`) nunca se estaba pasando también al lado CLI remoto vía `RESPF -ID=`. `mixed_ranging.py` usaba `session_id=1` para el iniciador local, pero `bridge.respf(...)` no incluía `ID`, así que el responder remoto quedaba con el default de la CLI (`ID=42`, visible en el volcado de parámetros de las cinco corridas anteriores: `SESSION_ID: 42`). **Este desalineamiento no está documentado en ninguna fuente oficial de Qorvo relevada** (ni el Developer Manual, ni la especificación `uwb-uci-messages-api`, ni `run_fira_twr.py`) — se descubrió comparando contra un proyecto hermano independiente, `uwb-qorvo-tools` (Raspberry Pi + un Qorvo local en modo UCI + Qorvo remotos por BLE/CLI, con esta misma arquitectura ya funcionando con ranging real medido). Ese proyecto documenta explícitamente (`ble_integration.md`) que los parámetros "session-wide" que se empujan a cada responder deben mantenerse "consistent with the initiator's UCI app config (session id, channel, block/round timing, initiator address)", y su código (`ble_session.py::respf_command`) arma `RESPF -ID={sid}` con el mismo id que usa `session_init` del lado UCI.

El fix fue trivial una vez identificado: `mixed_ranging.py` ahora pasa `ID=session_id` a `bridge.respf(...)`, igual que ya pasaba con `session_id` a `uci.session_init(...)`.

**Bitácora completa:**

1. **Corrida 1** (parámetros mínimos + clave STS, canal 9): timeout en ambos lados. El lado local solo mostraba 3 rondas en 8s — resultó ser un bug propio (ver recuadro en §2.3), no una señal real del hardware.
2. **Corrida 2** (+ `STS_LENGTH=1`, tras leer la Tabla 7.7 del Developer Manual): mismo resultado. Se descarta `STS_LENGTH` desalineado como causa única.
3. **Diagnóstico con `LISTENER`/`LSTAT`:** se confirmó tráfico UWB ajeno constante en canal 9 (casi seguro de otras placas de la misma flota `UWB-Node-1..9`).
4. **Corrida 3** (canal 5 en vez de 9): mismo resultado — se descarta la interferencia de canal como causa única.
5. **Corrida 4** (con el bug de `poll_notifications` corregido — ver §2.3): confirmó ~45 rondas reales por corrida (antes solo se observaban 3 por un bug de observación propio), pero las 45 seguían siendo `RANGING_RX_TIMEOUT`.
6. **Corrida 5** (paridad completa de `SESSION_SET_APP_CONFIG` con `run_fira_twr.py` del SDK — 7 parámetros nuevos: `AOA_RESULT_REQ`, `RESULT_REPORT_CONFIG`, `UWB_INITIATION_TIME`, `HOPPING_MODE`, `BLOCK_STRIDE_LENGTH`, `RSSI_REPORTING`, `MAX_NUMBER_OF_MEASUREMENTS`): el firmware aceptó los 25 parámetros sin rechazar ninguno, pero el resultado fue idéntico — timeout en cada ronda. Descartó definitivamente "falta un parámetro de `SESSION_SET_APP_CONFIG`" documentado en la spec oficial o en el script de referencia de Qorvo.
7. **Corrida 6 (éxito):** tras revisar `uwb-qorvo-tools` y encontrar la discrepancia de `session_id`/`RESPF -ID`, se agregó `ID=session_id` a `bridge.respf(...)` y `NUMBER_OF_CONTROLEES` (otro parámetro presente en la config de ese proyecto hermano, ausente en la nuestra) a `session_set_app_config()`. **Ranging real confirmado**, dos corridas consecutivas.

**Nota para reproducir:** si se vuelve a probar con canal 9 (compartido con la flota), es normal ver rondas `RANGING_RX_TIMEOUT` u otras entremezcladas con las `OK` por la interferencia real documentada en el punto 3 — lo relevante es que ahora **aparecen rondas `OK` con distancia**, cosa que nunca pasaba antes del fix.

## 5. Próximos pasos

- Las distancias reportadas (0-67cm en las corridas de prueba) confirman que el mecanismo funciona, pero **no son una medición de referencia calibrada** — falta la calibración de retardo de antena de la placa (fuera de alcance de este proyecto en su fase inicial, ver `CLAUDE.md` §1.1), así que hay un sesgo real esperable entre la distancia reportada y la distancia física exacta. Repetir esta comparación una vez que exista calibración, si se decide encarar esa fase.
- Si se necesita más de un responder remoto simultáneo, `uwb-qorvo-tools` documenta (validado contra hardware) que el modo *one-to-many* de esta firmware **no funciona** contra responders CLI (`RangingRxTimeout` en el 100% de las mediciones, y `RESPF -MULTI` es rechazado por el firmware CLI) — la estrategia que sí funciona es una sesión UCI unicast por cada responder (`session_id`, `session_id+1`, ...), cada una con su propio `RESPF -ID` remoto coincidente.

## 6. Qué no se automatizó (tests)

`tests/test_cli_bridge.py` cubre `CliBridgeClient` (construcción de comandos, manejo de errores) y el regex de detección de prompt, con un transporte falso — no requieren hardware ni una conexión BLE real. `mixed_ranging.py` no tiene test automatizado: orquesta dos transportes reales (USB + BLE) y su valor está en la corrida contra hardware real documentada en §4, no en una simulación.
