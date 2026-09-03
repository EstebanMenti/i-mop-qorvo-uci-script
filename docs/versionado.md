# Versionado y releases

> **Propósito:** definir cómo se versiona este proyecto, cómo se mantiene el `CHANGELOG.md` y cómo se etiqueta un release.
> **Alcance:** aplica desde el primer release publicado (`0.1.0`) en adelante. Este documento cubre un hueco que el proyecto hermano `i-mop-qorvo-CLI-script` no resolvió (no tiene `CHANGELOG.md`, `VERSION` ni tags de git) — se decidió resolverlo aquí desde el inicio.

---

## 1. Esquema de versión

**Semantic Versioning** (`MAJOR.MINOR.PATCH`), declarado en `pyproject.toml` (`project.version`) como única fuente de verdad del número de versión — no duplicar el número en otro archivo.

- **`MAJOR`**: cambio incompatible en la API pública del paquete (`UciClient`, `validation/spec.py`, subcomandos de `app/cli.py`) o en el formato del reporte de validación que rompa consumidores existentes.
- **`MINOR`**: nueva funcionalidad compatible hacia atrás (p. ej. nuevo comando UCI soportado, nuevo subcomando de CLI).
- **`PATCH`**: corrección de errores compatible hacia atrás (p. ej. fix de un parser, de un timeout, de framing).

Mientras la versión sea **`0.y.z`** (fase de diseño/implementación inicial, ver [plan-implementacion.md](plan-implementacion.md)), se aplica la convención habitual de SemVer para el rango `0.x`: cualquier cambio, incluso incompatible, puede ir en `MINOR`, y la API pública **no se considera estable** todavía. El proyecto pasa a `1.0.0` cuando la suite de validación (fase F6-F8 del plan) corre de punta a punta contra hardware real de forma reproducible.

## 2. Relación con Conventional Commits

El tipo de commit (ver [../CLAUDE.md §5.2](../CLAUDE.md#52-commits--conventional-commits-en-español)) orienta, pero no determina automáticamente, el número de versión del próximo release:

| Tipo de commit | Impacto habitual en versión |
|---|---|
| `fix` | `PATCH` |
| `feat` | `MINOR` |
| Cualquier tipo, si el cuerpo del commit indica `BREAKING CHANGE:` | `MAJOR` (o `MINOR` mientras el proyecto esté en `0.y.z`) |
| `docs`, `test`, `chore`, `refactor`, `perf` sin cambio de comportamiento observable | No amerita release por sí solo (se acumula en `[Unreleased]` hasta el próximo release) |

No se automatiza el cálculo de versión (no hay herramienta de *semantic-release* configurada); quien prepara el release decide el número aplicando esta tabla al conjunto de cambios acumulados.

## 3. `CHANGELOG.md`

Formato **[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)**. Estructura:

```markdown
## [Unreleased]

### Added
### Changed
### Fixed

## [0.2.0] - 2026-XX-XX

### Added
- ...
```

Reglas:

- Cada pull request que introduce un cambio visible (funcionalidad, fix, cambio de comportamiento) agrega su entrada bajo `[Unreleased]` **en el mismo PR**. Cambios puramente internos de documentación o tooling sin efecto para quien usa la herramienta pueden omitirse.
- Al preparar un release, las entradas de `[Unreleased]` se mueven a una nueva sección `## [X.Y.Z] - AAAA-MM-DD` (fecha en formato ISO 8601), y `[Unreleased]` queda vacío para el siguiente ciclo.
- Categorías admitidas: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security` (las de Keep a Changelog). Usar solo las que apliquen.

## 4. Etiquetado de un release (`git tag`)

1. Confirmar que `main` está verde (lint, tipos, tests — ver [../CLAUDE.md §2.3](../CLAUDE.md#23-testing)) y que `CHANGELOG.md` tiene la sección del release nueva.
2. Actualizar `project.version` en `pyproject.toml` al mismo número que el `CHANGELOG.md`, en un commit `chore(release): vX.Y.Z` mergeado a `main` por PR.
3. Crear un tag anotado sobre ese commit de `main`: `git tag -a vX.Y.Z -m "vX.Y.Z"` y `git push origin vX.Y.Z`.
4. Si el proyecto empieza a publicarse como paquete instalable fuera de este repositorio, evaluar en ese momento crear un GitHub Release a partir del tag, con el cuerpo del `CHANGELOG.md` de esa versión.

> **Nota:** hasta que exista una necesidad concreta de distribución externa, no es obligatorio crear GitHub Releases — el tag más la entrada del `CHANGELOG.md` son suficientes para trazabilidad interna.

## 5. Evidencia de validación vs. versionado del software

El versionado de este documento cubre el **código**. La evidencia de que una versión del software fue efectivamente probada contra hardware real (resultado de la suite de validación, capturas, hallazgos de firmware) se archiva por separado en `docs/resultados-validacion.md` y `docs/validaciones/` (ver fase F8 de [plan-implementacion.md](plan-implementacion.md)), siguiendo el mismo patrón que `i-mop-qorvo-CLI-script`. Cada acta de validación debe indicar contra qué versión del software (`vX.Y.Z` o commit) y qué versión/binario de firmware (`QM33SDK-1.1.1`, `*-UCI-FreeRTOS.hex`) se ejecutó.

## 6. Licencia y versión del SDK de referencia

Este proyecto es de **uso interno** (ver [../LICENSE](../LICENSE)) y no depende de compatibilidad de licencia para distribución externa mientras eso no cambie. Si en el futuro se evalúa publicarlo fuera de la organización, revisar antes:

- La licencia propietaria `LicenseRef-QORVO-2` del SDK de Qorvo (afecta qué se puede citar/incluir, no el código de este proyecto si fue reimplementado de forma independiente — ver [../CLAUDE.md §2.4](../CLAUDE.md#24-dependencias)).
- Actualizar este documento con la decisión de licencia tomada en ese momento.
