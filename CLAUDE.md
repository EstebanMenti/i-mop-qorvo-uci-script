# CLAUDE.md — Contexto y reglas del proyecto

> **Propósito de este archivo:** dar a cualquier asistente de IA (y a cualquier desarrollador nuevo) el contexto, las reglas de programación y las convenciones de trabajo de este repositorio. **Leer este archivo completo antes de modificar código o documentación.**
>
> Este documento sigue el mismo formato y espíritu que el `CLAUDE.md` de [i-mop-qorvo-CLI-script](https://github.com/EstebanMenti/i-mop-qorvo-CLI-script), adaptado al protocolo **UCI** en lugar de la consola de texto CLI.

---

## 1. Contexto del proyecto

### 1.1 Qué es

Herramienta de línea de comandos en **Python** para comunicarse por puerto serie con el módulo UWB **Qorvo DWM3001C** montado en la placa de desarrollo **DWM3001CDK**, cuando la placa corre el **firmware UCI** del SDK QM33 (release de referencia: `QM33SDK-1.1.1`, binario `SDK/Binaries/DWM3001CDK/*-UCI-FreeRTOS.hex`).

**UCI** (UWB Command Interface) es el protocolo binario estandarizado por el consorcio **FiRa** para controlar un chip UWB desde un host. Es un protocolo distinto de la consola de texto (`STAT`, `INITF`, `CALKEY`, ...) que expone el firmware `*-CLI-FreeRTOS.hex` — ambos viven en el mismo SDK pero son binarios de firmware separados que no corren a la vez en la misma placa.

La herramienta tiene **dos objetivos funcionales**:

1. **Probar la comunicación UCI de punta a punta**: abrir el transporte serie, enviar tramas UCI bien formadas y verificar que el firmware responde con el `Status` y el payload esperados.
2. **Validación automatizada de comandos**: ejecutar sistemáticamente los comandos UCI de los grupos `Core`, `Session`, `Ranging` (y, si aplica, `Test`) documentados en la especificación de mensajes UCI del SDK, comparar la respuesta contra lo esperado y generar un reporte (análogo al objetivo 1 de `i-mop-qorvo-CLI-script`, ver [docs/plan-implementacion.md](docs/plan-implementacion.md)).

La **calibración de retardo de antena** (objetivo 2 de la herramienta CLI hermana) queda **fuera de alcance** de este proyecto en su fase inicial: el firmware UCI expone esa funcionalidad, si existe, mediante extensiones propietarias de Qorvo (`GID` fuera del rango estándar FiRa) que no están cubiertas todavía por la documentación relevada. Ver nota en [docs/protocolo-uci.md](docs/protocolo-uci.md#6-extensiones-propietarias-de-qorvo).

### 1.2 Hardware del banco de pruebas

- Una o dos placas **DWM3001CDK** conectadas por USB a la misma PC (Windows). Cada placa expone un puerto COM virtual (USB CDC ACM).
- **Parámetros de puerto serie:** a confirmar contra la documentación del target `*-UCI-FreeRTOS.hex` — **no asumir** que son los mismos que usa el firmware CLI (115200 8N1). Ver tarea de verificación en [docs/plan-implementacion.md, fase F1](docs/plan-implementacion.md#f1--transporte-serie).
- Dos placas permiten probar una sesión de ranging real entre un dispositivo `Controller`/`Initiator` y uno `Controlee`/`Responder`.

### 1.3 Documentación de referencia (leerla antes de tocar la lógica del protocolo)

| Documento | Ubicación | Uso |
|---|---|---|
| UWB UCI Messages API | `SDK/Documentation/uwb-stack/uwb-uci-messages-api-*.pdf` (release QM33SDK-1.1.1) | **Fuente de verdad** del formato de mensajes UCI: framing, grupos de comando (GID), opcodes (OID), parámetros y códigos de estado. |
| UWB FiRa Protocol | `SDK/Documentation/uwb-stack/uwb-fira-protocol-*.pdf` | Especificación FiRa en la que se basa UCI: máquina de estados de sesión, parámetros de ranging. |
| DWM3001CDK Developer Manual | `SDK/Documentation/DeveloperManual/DWM3001CDK_Developer_Manual_QM33SDK-1.1.1.pdf` | Documenta la interfaz **CLI** de texto, no UCI — útil solo para contexto de hardware/puesta en marcha de la placa. |
| Resumen de protocolo relevado para este proyecto | [docs/protocolo-uci.md](docs/protocolo-uci.md) | Framing, tablas de GID/OID y códigos de estado ya extraídos y resumidos, con cita de la fuente. |
| Índice de referencias del fabricante | [docs/referencias/README.md](docs/referencias/README.md) | Dónde conseguir cada PDF y qué versión del SDK corresponde. |

**Regla:** ante cualquier duda sobre el protocolo (estructura de un mensaje, parámetros válidos, condiciones de un comando), la referencia es la especificación oficial de mensajes UCI. **No inventar comportamiento del firmware ni del protocolo.** Si algo no está confirmado contra la documentación oficial o contra hardware real, marcarlo **`[Sin confirmar]`** en la documentación y en los comentarios de código, y proponer cómo verificarlo.

### 1.4 Reglas de dominio críticas (errores frecuentes a evitar)

- El framing UCI (`MT`, `PBF`, `GID` en el byte 0; `OID` en el byte 1; longitud y payload después) **no es texto**: cualquier log o parser debe trabajar sobre bytes, nunca asumir que la respuesta es ASCII.
- `MT` (Message Type) distingue **Command** (host → dispositivo), **Response** (dispositivo → host, contesta un comando) y **Notification** (dispositivo → host, asíncrona, no es respuesta directa a un comando). El cliente debe poder correlacionar una `Response` con el `Command` que la originó (mismo `GID`/`OID`) y tratar las `Notification` (p. ej. `SESSION_STATUS_NTF`, `RANGING_DATA_NTF`) por un canal separado, ya que pueden llegar en cualquier momento.
- `PBF` (Packet Boundary Flag) indica fragmentación: un mensaje puede llegar en varios paquetes físicos. El parser de framing debe reensamblar antes de interpretar el payload — **nunca** asumir que un paquete físico es un mensaje UCI completo.
- No asumir la máquina de estados de sesión/ranging (p. ej. qué es válido antes de `SESSION_INIT` o `RANGING_START`) sin haber confirmado el estado real vía la notificación correspondiente (`DEVICE_STATUS_NTF`, `SESSION_STATUS_NTF`). No inferir el estado del dispositivo solo por lo que el script cree haber enviado.
- Existen `GID` propietarios de Qorvo (calibración, test de RF) por fuera del rango estándar FiRa. Tratarlos como una extensión opcional documentada aparte, nunca mezclarlos con la tabla de comandos estándar sin aclararlo.
- Cualquier comando que pueda alterar configuración persistente del dispositivo (si el firmware UCI expone un equivalente a `SAVE`/`RESTORE`/escritura de OTP) se trata con la misma precaución que en el proyecto hermano: **nunca** ejecutarlo desde código automatizado sin confirmación explícita del usuario.

---

## 2. Reglas de programación

### 2.1 Lenguaje y versión

- Python **≥ 3.11**. Desarrollo dentro de un **entorno virtual** (`.venv/` en la raíz, nunca versionado).
- Empaquetado con **`pyproject.toml`** (PEP 621). Instalación en modo editable: `pip install -e .[dev]`.

### 2.2 Estilo y calidad

- **Formato y lint:** `ruff` (formateador + linter). Línea máxima: 100 caracteres.
- **Tipado:** anotaciones de tipos obligatorias en toda función pública. Verificación con `mypy` (modo estricto en `src/`).
- **Docstrings:** obligatorios en módulos, clases y funciones públicas, **en español**, formato Google. Los identificadores (variables, funciones, clases, módulos) van **en inglés**.
- **Comentarios:** en español, solo para explicar restricciones no evidentes del protocolo (p. ej. "el firmware exige reensamblar por PBF antes de parsear"), nunca para narrar lo que el código ya dice.
- **Logging:** módulo `logging` (nunca `print` fuera de la capa `app/`). Todo el tráfico serie crudo (TX y RX, en hexadecimal) debe poder registrarse en archivo para diagnóstico — es la única forma de depurar un protocolo binario.
- **Errores:** jerarquía de excepciones propia con base `UciError` (p. ej. `UciTimeoutError`, `UciStatusError`, `UciFramingError`). Nunca capturar `Exception` sin re-lanzar o registrar. Un error de `Status` distinto de `OK` en una respuesta debe reportarse con el nombre simbólico del código (no solo el valor numérico).
- **Sin efectos colaterales peligrosos:** ninguna función debe enviar un comando que altere estado persistente del dispositivo sin que eso sea su propósito explícito y esté a la vista en su nombre.

### 2.3 Testing

- Framework: **pytest**. Los tests unitarios viven en `tests/` y **no requieren hardware**: la capa de transporte se simula con un transporte falso (`FakeTransport`) que reproduce tramas UCI reales capturadas de la placa (fixtures en bytes/hex, no texto).
- Los tests que sí requieren hardware real se marcan con `@pytest.mark.hardware` y se excluyen por defecto (`-m "not hardware"`).
- Todo codificador/decodificador de framing y todo parser de payload (por `GID`/`OID`) debe tener tests unitarios con tramas reales como casos, incluyendo casos de fragmentación (`PBF`) y de `Status` de error.
- Antes de cada commit: `ruff check`, `ruff format --check`, `mypy src`, `pytest -m "not hardware"` deben pasar.

### 2.4 Dependencias

- Mínimas y justificadas. Base prevista: `pyserial` (transporte), `typer` (CLI), `rich` (salida en consola/reportes). Evaluar `pyyaml` si la suite de validación usa specs declarativas en YAML. Dev: `pytest`, `ruff`, `mypy`.
- No agregar dependencias nuevas sin justificarlo en el pull request.
- **No copiar código fuente del SDK de Qorvo** (p. ej. la librería Python `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/` del release QM33SDK-1.1.1) hacia este repositorio. Esos archivos llevan la licencia propietaria `LicenseRef-QORVO-2` y **no está confirmado que permita redistribución o derivación** fuera del propio SDK. Usarla únicamente como **referencia de diseño** (para entender el framing y las tablas de GID/OID) y reimplementar de forma independiente en este proyecto. Ante cualquier duda de licenciamiento, consultar antes de portar código.

---

## 3. Estructura del repositorio

```
i-mop-qorvo-uci-script/
├── CLAUDE.md                  ← este archivo
├── README.md                  ← presentación y uso del proyecto
├── LICENSE                    ← uso interno / propietario
├── CHANGELOG.md               ← historial de versiones (Keep a Changelog)
├── .gitignore
├── pyproject.toml             ← (a crear en la fase F0, ver plan de implementación)
├── docs/                      ← documentación del proyecto (ver docs/README.md)
│   ├── README.md              ← índice de la documentación
│   ├── arquitectura.md        ← diseño del software
│   ├── protocolo-uci.md       ← resumen del protocolo UCI relevado del SDK
│   ├── plan-implementacion.md ← plan de implementación por fases
│   ├── versionado.md          ← política de versionado y releases
│   └── referencias/           ← índice de documentos oficiales del fabricante
├── src/
│   └── dwm3001c_uci/          ← paquete Python principal (a crear)
│       ├── transport/         ← capa serie: descubrimiento de puertos, lectura/escritura de bytes
│       ├── uci/                ← framing UCI, enums (GID/OID/Status), codec de payload
│       ├── core/               ← cliente UCI de alto nivel (comandos, correlación cmd↔resp, notificaciones)
│       ├── validation/         ← suite de validación declarativa + runner + reporte
│       └── app/                ← puntos de entrada de línea de comandos (Typer)
└── tests/                     ← tests pytest (sin hardware por defecto)
```

**Reglas de estructura:**

- Layout `src/`: el paquete importable vive solo bajo `src/`. Prohibido poner módulos sueltos en la raíz.
- Dependencias entre capas, en un solo sentido: `app → validation → core → uci → transport`. `transport` no conoce el protocolo UCI (solo mueve bytes); `uci` no conoce el transporte concreto ni Typer/Rich; `core` no conoce Typer/Rich. Detalle completo en [docs/arquitectura.md](docs/arquitectura.md).
- Los reportes generados en tiempo de ejecución van a `reports/` (ignorado por git) y los logs a `logs/` (ignorado por git).

---

## 4. Reglas de documentación

- **Idioma:** toda la documentación del proyecto se redacta **en español**.
- **Formato:** Markdown, con títulos numerados, tablas para datos enumerables (GID/OID, códigos de estado, parámetros), bloques `> **Nota/Advertencia**` para avisos, bloques de código para tramas y comandos.
- Todo documento nuevo en `docs/` debe: (a) empezar con un encabezado que indique propósito y alcance, (b) agregarse al índice `docs/README.md` **en el mismo pull request**.
- Las afirmaciones sobre el protocolo deben citar el documento y, si es posible, la sección de la especificación UCI/FiRa. Lo que no proviene de documentación oficial ni fue confirmado contra hardware real se marca **`[Sin confirmar]`**.
- El `README.md` de la raíz se mantiene sincronizado con la realidad del código: si cambia la interfaz de uso, se actualiza en el mismo pull request.
- El `CHANGELOG.md` se actualiza en el mismo pull request que introduce el cambio (ver política completa en [docs/versionado.md](docs/versionado.md)).

---

## 5. Flujo de trabajo con Git

### 5.1 Ramas

- `main`: siempre estable; solo recibe merges por pull request.
- Ramas de trabajo con el formato `<tipo>/<descripcion-corta-kebab-case>`:
  - `feature/` — nueva funcionalidad (ej.: `feature/uci-framing-codec`)
  - `fix/` — corrección de errores
  - `docs/` — solo documentación
  - `chore/` — mantenimiento, tooling, CI
  - `refactor/` — reestructuración sin cambio de comportamiento

> **Ramas `hardware/`:** para bancos de pruebas atados a hardware que no siempre está disponible, se pueden usar ramas de larga vida `hardware/<descripcion-corta-kebab-case>` que nunca se mergean a `main` (se sincronizan con `git merge origin/main`, nunca rebase) y documentan su propósito en `docs/`. Mismo patrón que `hardware/ble-bridge-nrf52840` en `i-mop-qorvo-CLI-script`.

### 5.2 Commits — Conventional Commits en español

Formato: `<tipo>(<ámbito opcional>): <descripción en imperativo, minúscula, sin punto final>`

- Tipos permitidos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`.
- Ámbitos sugeridos: `transport`, `uci`, `core`, `validation`, `app`, `docs`.
- La descripción va **en español**. Ejemplos:
  - `feat(uci): agrega codec de framing MT/PBF/GID/OID`
  - `fix(transport): corrige descubrimiento de puertos en Windows`
  - `docs: agrega tabla de códigos de estado a protocolo-uci.md`
- Commits atómicos: un cambio lógico por commit. No mezclar refactor con feature.
- No commitear: código comentado muerto, archivos generados, credenciales, `.venv/`, `reports/` ni `logs/`.
- Los commits que ameriten un cambio de versión (ver [docs/versionado.md](docs/versionado.md)) deben dejarlo claro en el cuerpo del mensaje o en el PR asociado.

### 5.3 Pull requests

- Todo cambio a `main` pasa por PR, incluso siendo un solo desarrollador (deja trazabilidad).
- El título del PR sigue el mismo formato que los commits.
- La descripción debe incluir: **qué** cambia, **por qué**, **cómo se probó** (contra hardware real o solo con transporte simulado), y captura del reporte o traza serie cuando aplique.
- Requisitos para mergear: lint, tipos y tests en verde; documentación y `CHANGELOG.md` actualizados si el cambio los afecta.
- Merge por *squash* si la rama tiene commits de corrección intermedios; merge normal si los commits son atómicos y valiosos.

---

## 6. Versionado y releases

Este proyecto usa **Semantic Versioning** (`MAJOR.MINOR.PATCH`) y mantiene un `CHANGELOG.md` siguiendo el formato **Keep a Changelog**. La política completa (cuándo subir cada número, cómo se etiqueta un release con `git tag`, y qué evidencia de validación se archiva) está en **[docs/versionado.md](docs/versionado.md)** — leerla antes de preparar cualquier release o de decidir si un cambio es `fix`, `feat` o rompe compatibilidad.

---

## 7. Reglas para asistentes de IA

1. **No inventar comportamiento del firmware ni del protocolo UCI.** Ante una duda, consultar `docs/protocolo-uci.md` y la especificación oficial citada; si no está confirmado, decirlo explícitamente (`[Sin confirmar]`) y proponer verificación contra hardware real.
2. **No copiar código fuente del SDK de Qorvo** (licencia propietaria `LicenseRef-QORVO-2`) hacia este repositorio; usarlo solo como referencia de diseño. Ver [§2.4](#24-dependencias).
3. **Seguir el plan:** la implementación se rige por `docs/plan-implementacion.md`. No agregar módulos, dependencias ni funcionalidades fuera del plan sin consultar antes al responsable del proyecto.
4. **No ejecutar comandos que alteren estado persistente del dispositivo** (configuración guardada, OTP, o cualquier equivalente UCI de `RESTORE`/`SAVE`) desde código automatizado sin confirmación explícita e interactiva del usuario.
5. Mantener la coherencia de idioma: documentación, docstrings, comentarios y commits en español; identificadores en inglés.
6. Ante ambigüedad en un requisito o en el protocolo, **preguntar antes de implementar**; no decidir unilateralmente.
