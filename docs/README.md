# Documentación del proyecto — Índice

> **Propósito:** punto de entrada a toda la documentación del proyecto `dwm3001c-uci`.
> **Convención:** todos los documentos se redactan en español, en Markdown, con el mismo estilo técnico (títulos numerados, tablas, notas `> **Nota**`). Lo que no proviene de documentación oficial de Qorvo/FiRa ni fue confirmado contra hardware real se marca **`[Sin confirmar]`**.

---

## 1. Documentos del proyecto

| Documento | Contenido | Audiencia |
|---|---|---|
| [../README.md](../README.md) | Presentación, instalación y uso previsto de la herramienta | Usuarios |
| [../CLAUDE.md](../CLAUDE.md) | Contexto, reglas de programación, estructura y flujo de trabajo con Git | Desarrolladores / IA |
| [arquitectura.md](arquitectura.md) | Diseño del software: capas, módulos, responsabilidades y flujo de datos | Desarrolladores |
| [protocolo-uci.md](protocolo-uci.md) | Resumen del protocolo UCI relevado del SDK: framing, grupos de comando (GID/OID), códigos de estado, extensiones propietarias de Qorvo | Desarrolladores |
| [plan-implementacion.md](plan-implementacion.md) | Plan de implementación por fases, con criterios de aceptación | Desarrolladores / IA implementadora |
| [versionado.md](versionado.md) | Política de versionado semántico, `CHANGELOG.md`, etiquetado de releases y archivo de evidencia de validación | Desarrolladores / mantenedores |
| [resultados-validacion.md](resultados-validacion.md) | Acta de la primera corrida completa de la suite de validación (F0–F6) contra hardware real: 11/11 checks OK, hallazgos de firmware y evidencia archivada en [validaciones/](validaciones/) | Todos |

## 2. Documentos de referencia (fabricante)

Ubicados en [referencias/](referencias/README.md), con su propio índice.

## 3. Cómo agregar un documento

1. Redactarlo en español siguiendo el estilo de los documentos existentes.
2. Iniciarlo con un encabezado `>` que indique **propósito** y **alcance**.
3. Agregarlo a la tabla correspondiente de este índice en el mismo pull request.
4. Si el documento hace afirmaciones sobre el protocolo o el firmware, citar la fuente oficial o marcarlas `[Sin confirmar]`.
