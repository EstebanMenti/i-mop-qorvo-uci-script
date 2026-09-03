# Referencias del fabricante — índice

> **Propósito:** indicar qué documentos oficiales de Qorvo/FiRa respaldan las afirmaciones de este proyecto sobre el protocolo UCI, y dónde conseguirlos.
> **Alcance:** metadatos y ubicación de los documentos. **Los PDF no están vendorizados en este repositorio todavía** (ver nota al final).

---

## 1. Documentos identificados (release `QM33SDK-1.1.1`)

| Documento | Ubicación en el release del SDK | Uso |
|---|---|---|
| UWB UCI Messages API | `SDK/Documentation/uwb-stack/uwb-uci-messages-api-R12.7.0-405.pdf` | **Fuente de verdad** del formato de mensajes UCI — base de [../protocolo-uci.md](../protocolo-uci.md). |
| UWB FiRa Protocol | `SDK/Documentation/uwb-stack/uwb-fira-protocol-R12.7.0-405.pdf` | Especificación FiRa subyacente: máquina de estados de sesión y ranging. |
| UWB L1 API / L1 Configuration | `SDK/Documentation/uwb-stack/uwb-l1-api-*.pdf`, `uwb-l1-configuration-*.pdf` | Configuración de capa física, referencia para parámetros de `SET_CONFIG`/`SESSION_SET_APP_CONFIG`. |
| UWB QHAL / QOSAL / QPLATFORM API | `SDK/Documentation/uwb-stack/uwb-qhal-api-*.pdf`, `uwb-qosal-api-*.pdf`, `uwb-qplatform-api-*.pdf` | Capas internas del stack de Qorvo — solo contexto, no protocolo de aplicación. |
| DWM3001CDK Developer Manual | `SDK/Documentation/DeveloperManual/DWM3001CDK_Developer_Manual_QM33SDK-1.1.1.pdf` | Documenta la interfaz **CLI** de texto (firmware distinto). Útil solo para hardware/puesta en marcha de la placa. |
| Quick Start Guide DWM3001CDK | `SDK/Documentation/QuickStartGuide/*.pdf` | Conectores y puesta en marcha de la placa. |

Release de origen: repositorio `i-mop-qorvo-uci-fw`, carpeta `DW3_QM33_SDK_1.1.1/SDK/Documentation/`.

## 2. Estado de disponibilidad en este repositorio

Estos PDF **no fueron copiados** a `docs/referencias/` de este repositorio. Antes de vendorizarlos (como hace `i-mop-qorvo-CLI-script` con sus notas de aplicación):

1. Confirmar que la licencia `LicenseRef-QORVO-2` del SDK permite redistribuir estos documentos dentro de un repositorio interno de la organización.
2. Si se confirma, copiarlos a `docs/referencias/` con el mismo nombre de archivo que en el release, y agregar la fila correspondiente a este índice con el enlace relativo (siguiendo el patrón de `docs/referencias/` en el proyecto hermano).

Mientras tanto, cualquier cita a estos documentos en la documentación del proyecto debe referenciar la ruta dentro del release del SDK (como en la tabla de arriba), no un enlace local inexistente.
