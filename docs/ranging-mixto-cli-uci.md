# Ranging mixto: placa UCI (local, USB) + placa CLI (remota, BLE)

> **Propósito:** documentar la herramienta experimental que intenta un ranging real entre una placa local con firmware UCI (nuestro `UciClient`, por USB) y una placa remota con firmware CLI de texto, controlada por Bluetooth a través del puente `I-mop-nrf52840-fw`.
> **Alcance:** arquitectura de `cli_bridge/` y `mixed_ranging.py`, cómo usarlos, y el resultado real de la primera corrida contra hardware (positivo en conectividad/protocolo, sin éxito todavía en la medición física de distancia).

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

## 4. Resultado contra hardware real (cinco corridas)

**Fecha:** 2026-09-03. **Placas:** local en `COM29` (firmware UCI), remota `UWB-Node-2` (DWM3001CDK detrás de un puente nRF52840, firmware CLI `1.1.0`, build `Aug 10 2026`, `UWB stack: R12.7.0-405-gb33c5c4272`). **Confirmado por el usuario:** ambas placas están físicamente cerca y sin obstáculos — se descarta distancia/obstrucción como causa.

**✅ Positivo, estable en las cinco corridas — toda la plomería funciona de punta a punta:**

- Escaneo y conexión BLE al puente (`UWB-Node-2`, dirección `FE:79:A2:F3:52:B9`).
- `qorvo on` encendió el Qorvo remoto; `qorvo STAT` devolvió el JSON de estado real.
- `qorvo RESPF -CHAN=<N> -PCODE=10 -RRU=DSTWR -ADDR=1 -PADDR=0` arrancó el responder remoto y devolvió el volcado completo de parámetros FiRa — coincidiendo campo a campo con lo esperado (`STATIC_STS_IV: "01:02:03:04:05:06"`, `VENDOR_ID: "07:08"`, etc.), en canal 9 y en canal 5.
- El lado local completó `SESSION_INIT` → `SESSION_SET_APP_CONFIG` (`Status.OK`, sin parámetros rechazados) → `RANGING_START` (`Status.OK`, sesión pasó a `ACTIVE`).

**❌ No logrado, en las cinco corridas — el ranging físico real:** ambos lados reportan timeout en cada ronda (remoto: `SESSION_INFO_NTF` con `status="RX_TIMEOUT"`; local: `TwrMeasurement` con `status=RANGING_RX_TIMEOUT`). Ninguna ronda devolvió una distancia real.

**Bitácora de las cuatro corridas:**

1. **Corrida 1** (parámetros mínimos + clave STS, canal 9): timeout en ambos lados. El lado local solo mostraba 3 rondas en 8s — resultó ser un bug propio (ver recuadro en §2.3), no una señal real del hardware.
2. **Corrida 2** (+ `STS_LENGTH=1`, tras leer la Tabla 7.7 del Developer Manual): mismo resultado. Se descarta `STS_LENGTH` desalineado como causa única — el resto de los campos de esa tabla para `BPRF4` (`SYNC PSR=64`, `SFD#=2`, `SFD Length=8`, `STS nr of Segments=1`) ya coincidían o son defaults estándar compartidos.
3. **Diagnóstico con `LISTENER`/`LSTAT`:** se puso el Qorvo remoto en modo sniffer (`qorvo LISTENER`) para ver si recibía **algo** por aire. **Hallazgo:** recibía tramas UWB constantes en canal 9 (una cada ~200-300 ms, `rsl`/`fsl` entre -70 y -85 dBm, contenido repetitivo) **antes incluso de que el lado local empezara a rangear** — hay tráfico ajeno real en ese canal, casi seguro de otras placas de la misma flota (`UWB-Node-1..9`) rangeando en simultáneo.
4. **Corrida 3** (canal 5 en vez de 9, para evitar la interferencia detectada): mismo resultado — timeout en ambos lados. La interferencia en canal 9 es real pero **no es la causa** de este problema puntual (o no la única).
5. **Corrida 4** (con el bug de `poll_notifications` corregido — ver §2.3): la corrida de 8s ahora sí mostró las ~45 rondas reales (antes solo 3), confirmando que el fix de observación funciona. **Pero las 45 rondas reales fueron igual de `RANGING_RX_TIMEOUT` que antes** — no era un problema de que "no veíamos" las rondas exitosas: genuinamente no hay ninguna.

**Conclusión hasta ahora:** se descartaron, con evidencia contra hardware real, distancia física, `STS_LENGTH`, interferencia de canal (al menos como causa única) y un bug real de observación del lado del cliente (ya corregido, mejora quede). El resto de los parámetros documentados (canal, preámbulo, RRU, timing, clave STS completa) coinciden byte a byte entre ambos lados. **La causa de fondo sigue sin identificarse.**

**Hipótesis restantes para una próxima iteración:**

1. ~~Parámetros PHY más finos del perfil `BPRF4` no cubiertos por el subconjunto de `App.defs` que implementa este proyecto~~ — parcialmente resuelto, ver corrida 5 abajo: se leyó completa la Tabla 7.2 de la especificación oficial `uwb-uci-messages-api` y se comparó `session_set_app_config()` contra `run_fira_twr.py` del SDK (el script de referencia *propio de Qorvo* para correr TWR por UCI, no la CLI). Quedan sin cubrir parámetros que ese mismo script de referencia tampoco fija explícitamente (`PSDU_DATA_RATE`, `PREAMBLE_DURATION`, `PRF_MODE`, `RANGING_ROUND_CONTROL`) — al no estar en la lista "mandatory" de Qorvo, se asume que su default de firmware ya es el correcto y no se agregan por ahora.
2. ~~`UWB_INITIATION_TIME`/otros parámetros de sincronización fina no controlados explícitamente por ninguno de los dos lados~~ — resuelto en corrida 5: ahora se fija explícitamente (`UWB_INITIATION_TIME=0`, igual que el default de `run_fira_twr.py`).
3. Alguna diferencia de comportamiento entre el motor FiRa tal como lo maneja el firmware CLI (vía "helpers API", llamada local) y el motor tal como lo maneja el firmware UCI (vía protocolo binario) que no sea puramente de configuración — es decir, que la premisa "ambos usan la misma uwb-stack, solo cambia la interfaz de control" (confirmada arquitectónicamente en el Developer Manual, ver `docs/plan-implementacion.md`) tenga alguna excepción no documentada. **Sigue sin descartarse.**
4. Interferencia de canal como factor agravante (no descartada del todo, solo como causa única) — repetir con la flota de otras placas apagada, si es posible coordinarlo. **Sigue sin descartarse.**

### Corrida 5 (planeada): paridad completa con `run_fira_twr.py`

Tras las cuatro corridas de arriba, se releyó la especificación oficial completa
`uwb-uci-messages-api-R12.7.0-405.pdf` (Tabla 7.2, "Application Configuration
Parameters") y se comparó `session_set_app_config()` de este proyecto contra
`run_fira_twr.py` del SDK Qorvo (`SDK/Tools/uwb-qorvo-tools/scripts/fira/`),
que es la implementación de referencia **propia de Qorvo** para correr una
sesión de TWR por UCI (mismo protocolo que este proyecto, no la CLI de
texto). Ese script arma su lista de `app_configs` con 22-23 parámetros en
toda corrida; este proyecto solo enviaba 18. Los 7 que faltaban y ya se
agregaron (`AOA_RESULT_REQ`, `RESULT_REPORT_CONFIG`, `UWB_INITIATION_TIME`,
`HOPPING_MODE`, `BLOCK_STRIDE_LENGTH`, `RSSI_REPORTING`,
`MAX_NUMBER_OF_MEASUREMENTS`), con los mismos valores por defecto que usa ese
script (ver `core/client.py::session_set_app_config`).

**`[Sin confirmar]`**: no se descarta que alguno de estos parámetros —
particularmente `RESULT_REPORT_CONFIG` (qué campos incluye el mensaje final
de reporte de la ronda DS-TWR) o `AOA_RESULT_REQ` — sea la causa real del
`RANGING_RX_TIMEOUT` persistente si el firmware CLI remoto y el firmware UCI
local terminan con valores de firmware-default distintos para alguno de
ellos al no fijarlos explícitamente. Esta es una hipótesis, no un hallazgo:
falta la quinta corrida contra hardware real para confirmar o descartar.

**Resultado de la corrida 5 (2026-09-03, mismo hardware que las cuatro
anteriores):** el firmware local aceptó los 25 parámetros sin rechazar
ninguno (`session_set_app_config` devolvió `Status.OK`, `rejected=()`,
`RANGING_START` pasó a `ACTIVE` normalmente). El volcado de `RESPF` remoto
mostró los mismos valores de siempre (`STATIC_STS_IV`, `VENDOR_ID`, canal,
`RRU`, timing — todo coincide). **El resultado de ranging fue idéntico a las
cuatro corridas anteriores:** 45 rondas observadas del lado local en 8s,
las 45 con `status=RANGING_RX_TIMEOUT`; el lado remoto mostró la misma
cantidad de `SESSION_INFO_NTF` con `status="RX_TIMEOUT"`. **Se descarta la
hipótesis de "faltaba un parámetro de `SESSION_SET_APP_CONFIG`"**: se llegó
a la paridad completa con la implementación de referencia oficial de Qorvo
para UCI (`run_fira_twr.py`) y el resultado no cambió en absoluto.

**Replanteo tras la corrida 5:** con dos fuentes independientes agotadas (la
especificación oficial completa y el script de referencia oficial de Qorvo
para UCI), la evidencia ahora apunta con más fuerza a la hipótesis 3 de
arriba — una diferencia real entre el camino CLI (`RESPF`/`INITF`, código C
del firmware que no está disponible como fuente en este SDK) y el camino UCI
(protocolo binario), más que a un parámetro de configuración faltante. Un
diagnóstico decisivo y todavía no probado: **repetir este mismo
`session_set_app_config`/`ranging_start` entre dos placas que corran ambas
firmware UCI** (sin ningún CLI/BLE de por medio). Si ese caso funciona
(mide distancia real), confirma que la lógica de este cliente es correcta y
aísla el problema al puente CLI↔UCI. Si también falla, el problema está en
cómo este cliente arma la sesión, no en la mezcla CLI/UCI. Pendiente:
conseguir una segunda placa con firmware UCI para esta prueba.

## 5. Qué no se automatizó (tests)

`tests/test_cli_bridge.py` cubre `CliBridgeClient` (construcción de comandos, manejo de errores) y el regex de detección de prompt, con un transporte falso — no requieren hardware ni una conexión BLE real. `mixed_ranging.py` no tiene test automatizado: orquesta dos transportes reales (USB + BLE) y su valor está en la corrida contra hardware real documentada en §4, no en una simulación.
