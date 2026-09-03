# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Semantic Versioning](https://semver.org/lang/es/) — ver la política completa en [docs/versionado.md](docs/versionado.md).

## [Unreleased]

### Added

- Documentación inicial de arquitectura, protocolo UCI, plan de implementación, flujo de trabajo con Git y política de versionado (`CLAUDE.md`, `docs/`). Todavía no hay código implementado — ver [docs/plan-implementacion.md](docs/plan-implementacion.md).
- Setup del proyecto (fase F0): `pyproject.toml`, layout `src/dwm3001c_uci/` con los paquetes `transport/`, `uci/`, `core/`, `validation/`, `app/`.
- Capa de transporte (fase F1): `SerialLink` (pyserial) y descubrimiento de puertos serie candidatos.
- Framing y enums UCI (fase F2): codificación/decodificación de tramas (`MT`/`PBF`/`GID`/`OID`), fragmentación y reensamblado de mensajes (`StreamDecoder`), y los enums `Gid`, `OidCore`, `OidSession`, `OidRanging`, `OidTest`, `Status` confirmados contra el SDK QM33 1.1.1.
- Valores exactos de `Status` corregidos en `docs/protocolo-uci.md` tras verificarlos por lectura directa de la fuente del SDK (algunos códigos habían quedado mal estimados en el resumen inicial).
