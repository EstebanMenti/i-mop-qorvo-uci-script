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

> **Nota — reensamblado:** cuando `PBF = 1`, el mensaje lógico continúa en el/los paquete(s) siguiente(s) con el mismo `GID`/`OID`; el consumidor debe reensamblar antes de decodificar el payload. El tamaño exacto de payload por paquete antes de fragmentar **`[Sin confirmar]`** — verificar el valor exacto contra la especificación de mensajes UCI antes de fijarlo como constante en el código.

## 2. Grupos de comando (GID) y opcodes (OID)

| GID | Nombre | OID principales relevados |
|---|---|---|
| `0x00` | `Core` | `RESET` (`0x00`), `DEVICE_STATUS_NTF` (`0x01`, notificación), `GET_DEVICE_INFO` (`0x02`), `GET_CAPS` (`0x03`), `SET_CONFIG` (`0x04`), `GET_CONFIG` (`0x05`), `GENERIC_ERROR_NTF` (`0x07`, notificación), `GET_TIME` (`0x08`) |
| `0x01` | `Session` | `INIT` (`0x00`), `DEINIT` (`0x01`), `STATUS_NTF` (`0x02`, notificación), `SET_APP_CONFIG` (`0x03`), `GET_APP_CONFIG` (`0x04`), `GET_COUNT` (`0x05`), `GET_STATE` (`0x06`), `UPDATE_MULTICAST_LIST` (`0x07`), `SET_ANCHOR_RANGING_ROUNDS` (`0x08`), `SET_TAG_ACTIVITY` (`0x09`), `GET_DATA_SIZE` (`0x0B`), `UPDATE_HUS` (`0x0C`) |
| `0x02` | `Ranging` | `START` (`0x00`), `STOP` (`0x01`), `GET_COUNT` (`0x03`), `DATA_CREDIT` (`0x04`), `DATA_TRANSFER_STATUS` (`0x05`) |
| `0x0D` | `Test` | `CONFIG_SET` (`0x00`), `CONFIG_GET` (`0x01`), `PERIODIC_TX` (`0x02`), `PER_RX` (`0x03`), `RX` (`0x05`), `LOOPBACK` (`0x06`), `STOP_SESSION` (`0x07`), `SS_TWR` (`0x08`) |
| *(propietario)* | `Qorvo` / `Calibration` | Ver [§6](#6-extensiones-propietarias-de-qorvo). |

> **Nota:** esta tabla es un resumen orientativo extraído de la implementación de referencia. Antes de implementar el codec de un comando concreto, confirmar los campos del payload contra `uwb-uci-messages-api-*.pdf`.

## 3. Notificaciones a manejar de forma asíncrona

Al menos las siguientes `Notification` pueden llegar sin estar correlacionadas 1:1 con el último comando enviado, y el cliente debe poder despacharlas por separado (ver [arquitectura.md §3.3](arquitectura.md#33-core)):

- `CORE_DEVICE_STATUS_NTF` (`GID=0x00`, `OID=0x01`)
- `CORE_GENERIC_ERROR_NTF` (`GID=0x00`, `OID=0x07`)
- `SESSION_STATUS_NTF` (`GID=0x01`, `OID=0x02`)
- Notificaciones de datos de ranging (nombre exacto y `OID` **`[Sin confirmar]`** — verificar contra la especificación; en la CLI de texto del proyecto hermano el equivalente es `SESSION_INFO_NTF`).

## 4. Códigos de estado (`Status`)

| Categoría | Valores relevados |
|---|---|
| Genéricos | `OK` (`0x00`), `REJECTED`, `FAILED`, `SYNTAX_ERROR`, `INVALID_PARAM`, `INVALID_RANGE`, `INVALID_MESSAGE_SIZE`, `UNKNOWN_GID`, `UNKNOWN_OID`, `READ_ONLY`, `COMMAND_RETRY` |
| Sesión | `ERROR_SESSION_NOT_EXIST`, `ERROR_SESSION_DUPLICATE`, `ERROR_SESSION_ACTIVE`, `ERROR_MAX_SESSIONS_EXCEEDED`, `ERROR_MULTICAST_LIST_FULL` |
| Ranging | `RANGING_TX_FAILED`, `RANGING_RX_TIMEOUT`, `RANGING_RX_PHY_DEC_FAILED`, entre otros |
| Propietario | Rango `0x50`–`0xFF` reservado para códigos específicos de Qorvo (ej. `ERROR_SE_BUSY`) |

Toda respuesta con `Status != OK` debe reportarse en logs y en el reporte de validación con el **nombre simbólico**, no solo el valor numérico (ver [../CLAUDE.md §2.2](../CLAUDE.md#22-estilo-y-calidad)).

## 5. Transporte

- El transporte confirmado para el protocolo UCI en este SDK es **UART** sobre el puerto COM virtual (USB CDC ACM) de la placa. No se relevó soporte de SPI a nivel de framing UCI del host (SPI se usa a nivel del driver del transceptor DW3xxx, capa distinta y fuera de alcance de este proyecto).
- Parámetros exactos del puerto serie (baud rate, bits, paridad) para el binario `*-UCI-FreeRTOS.hex` **`[Sin confirmar]`** — no asumir que son los mismos que usa el firmware CLI de texto (115200 8N1). Confirmar contra la documentación del SDK antes de fijarlos como default (tarea de la fase F1 del plan de implementación).

## 6. Extensiones propietarias de Qorvo

El SDK define grupos de comando (`GID`) y comandos adicionales fuera del estándar FiRa, para funciones de fábrica/depuración: pruebas de RF (`test_tx_cw`, `test_pll_lock`, `test_tof`, `test_rtc`) y gestión de calibración (`get_cal`/`set_cal`, con claves del estilo `ant<x>.ch<y>.ant_delay`, conceptualmente equivalentes a `CALKEY`/`LISTCAL` de la CLI de texto).

Estas extensiones **quedan fuera del alcance inicial** de este proyecto (ver [../CLAUDE.md §1.1](../CLAUDE.md#11-qué-es)). Si en el futuro se decide cubrirlas, deben documentarse en un anexo separado de este archivo, citando la fuente, y no mezclarse con las tablas de comandos estándar de arriba.

## 7. Nota legal sobre el código fuente de referencia

La librería Python `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/*.py` usada para confirmar las tablas de este documento lleva la cabecera `SPDX-License-Identifier: LicenseRef-QORVO-2` (licencia propietaria de Qorvo). **No está confirmado que esa licencia permita copiar o derivar código hacia este repositorio.** Esta herramienta reimplementa el codec de forma independiente, usando esos archivos únicamente como referencia de lectura para entender y verificar el protocolo. Ver regla explícita en [../CLAUDE.md §2.4](../CLAUDE.md#24-dependencias).
