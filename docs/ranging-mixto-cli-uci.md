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
| **`VENDOR_ID`** | `0x0708` | Agregado a `session_set_app_config()` en esta iteración — antes no se fijaba explícitamente del lado UCI |
| **`STATIC_STS_IV`** | `01:02:03:04:05:06` | idem — clave STS estática compartida, necesaria para que dos dispositivos en modo STS estático (`STS_CONFIG=0`) se "escuchen" |
| Direcciones MAC | Local `0x0000` (Controller/Initiator), remota `0x0001` (Controlee/Responder) | Coincide con los defaults de `RESPF` (`ADDR=1, PADDR=0`) |

## 4. Resultado de la primera corrida contra hardware real

**Fecha:** 2026-09-03. **Placas:** local en `COM29` (firmware UCI), remota `UWB-Node-2` (DWM3001CDK detrás de un puente nRF52840, firmware CLI `1.1.0`, build `Aug 10 2026`).

**✅ Positivo — toda la plomería funcionó de punta a punta, sin ningún ajuste:**

- Escaneo y conexión BLE al puente (`UWB-Node-2`, dirección `FE:79:A2:F3:52:B9`).
- `qorvo on` encendió el Qorvo remoto; `qorvo STAT` devolvió el JSON de estado real.
- `qorvo RESPF -CHAN=9 -PCODE=10 -RRU=DSTWR -ADDR=1 -PADDR=0` arrancó el responder remoto y devolvió el volcado completo de parámetros FiRa — coincidiendo campo a campo con lo esperado (`STATIC_STS_IV: "01:02:03:04:05:06"`, `VENDOR_ID: "07:08"`, etc.).
- Las notificaciones asíncronas del lado remoto (`SESSION_STATUS_NTF`, `SESSION_INFO_NTF`) quedaron capturadas dentro de la misma respuesta BLE del comando `RESPF` (confirma lo dicho en §2.3: el bridge no las descarta si llegan dentro de su ventana de captura).
- El lado local completó `SESSION_INIT` → `SESSION_SET_APP_CONFIG` (`Status.OK`, sin parámetros rechazados) → `RANGING_START` (`Status.OK`, sesión pasó a `ACTIVE`).

**❌ No logrado — el ranging físico real:**

- **Ambos lados** reportaron timeout en cada ronda: el lado remoto (`SESSION_INFO_NTF`) con `status="RX_TIMEOUT"` contra `mac_address=0x0000` (la placa local), y el lado local (`TwrMeasurement` decodificado de `RANGING_DATA_NTF`) con `status=RANGING_RX_TIMEOUT` contra `mac_address=00:01` (la placa remota). Ninguna ronda devolvió una distancia real.
- El lado local dejó de recibir `RANGING_DATA_NTF` después de las primeras rondas (se observaron 3, no las ~40 esperadas en 8 s a 200 ms/ronda) — comportamiento distinto al de una sesión sin ningún par real (que sí sigue emitiendo una notificación por ronda de forma constante, ver `docs/referencia-comandos-uci.md` §4.1). Sugiere algún tipo de interacción a nivel MAC entre los dos dispositivos reales (colisión, backoff) que no se investigó en profundidad todavía.

**Hipótesis para una próxima iteración (sin confirmar, orden sugerido de investigación):**

1. **Perfil PRF (`PRFSET=BPRF4` en la CLI):** agrupa varios parámetros PHY (tasa de datos PSDU, duración de preámbulo, tasa de PHR) que `session_set_app_config()` no fija explícitamente del lado UCI — podrían no coincidir con el perfil BPRF4 aunque los campos que sí controlamos (`SFD_ID`, `PCODE`, `RFRAME_CONFIG`) coincidan.
2. **Distancia/obstrucción física real** entre las dos placas al momento de la prueba — no verificada; UWB tiene alcance corto y es sensible a obstáculos.
3. Revisar si `UWB_INITIATION_TIME`/otros parámetros de sincronización fina (no controlados por ninguno de los dos lados explícitamente) requieren alineación.

## 5. Qué no se automatizó (tests)

`tests/test_cli_bridge.py` cubre `CliBridgeClient` (construcción de comandos, manejo de errores) y el regex de detección de prompt, con un transporte falso — no requieren hardware ni una conexión BLE real. `mixed_ranging.py` no tiene test automatizado: orquesta dos transportes reales (USB + BLE) y su valor está en la corrida contra hardware real documentada en §4, no en una simulación.
