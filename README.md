# dwm3001c-uci

> Herramienta de línea de comandos en **Python** para probar la comunicación **UCI** (Ultra-Wideband Command Interface, protocolo binario basado en FiRa) con el módulo UWB **Qorvo DWM3001C**, cuando la placa de desarrollo **DWM3001CDK** corre el **firmware UCI** del SDK QM33 (release de referencia: `QM33SDK-1.1.1`, variante `*-UCI-FreeRTOS.hex`).

## Estado del proyecto

**En fase de diseño.** Este repositorio contiene por ahora las reglas de arquitectura, protocolo y flujo de trabajo que van a guiar la implementación (ver [docs/](docs/README.md)); el código todavía no existe. El plan de implementación por fases está en [docs/plan-implementacion.md](docs/plan-implementacion.md).

## Qué va a hacer

1. **Probar la comunicación UCI de punta a punta**: abrir el puerto serie de la placa, enviar comandos UCI (`CORE_GET_DEVICE_INFO`, `CORE_GET_CAPS`, `SESSION_INIT`, `RANGING_START`, etc.) y verificar que las respuestas y notificaciones tengan el formato y contenido esperado.
2. **Automatizar una suite de validación** de los comandos UCI documentados en la especificación de mensajes UCI/FiRa del SDK, generando un reporte de resultados (análogo al objetivo de validación de [i-mop-qorvo-CLI-script](https://github.com/EstebanMenti/i-mop-qorvo-CLI-script), pero contra el protocolo binario en lugar de la consola de texto).

No es un reemplazo del script CLI existente: ese proyecto habla con el firmware **CLI** de texto; este habla con el firmware **UCI** binario del mismo SDK. Son firmwares distintos (`*-CLI-FreeRTOS.hex` vs `*-UCI-FreeRTOS.hex`) que no corren simultáneamente en la misma placa.

## Hardware requerido

- Placa **DWM3001CDK** con el firmware `*-UCI-FreeRTOS.hex` de `QM33SDK-1.1.1` flasheado.
- Cable USB — la placa expone un puerto COM virtual (USB CDC ACM).
- Opcional: una segunda placa DWM3001CDK para probar sesiones de ranging entre dos dispositivos (`Controller`/`Controlee`).

## Instalación (cuando el código esté implementado)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Uso previsto

```bash
dwm-uci ports              # lista puertos serie candidatos
dwm-uci info                # CORE_GET_DEVICE_INFO / CORE_GET_CAPS
dwm-uci validate            # corre la suite de validación de comandos UCI
```

La interfaz definitiva se documenta en el mismo pull request que la implemente (ver regla de sincronización en [CLAUDE.md](CLAUDE.md#4-reglas-de-documentación)).

## Documentación

Punto de entrada completo: [docs/README.md](docs/README.md). Para empezar:

| Si querés... | Leé |
|---|---|
| Entender las reglas de contribución, dominio y flujo de trabajo | [CLAUDE.md](CLAUDE.md) |
| Entender el diseño del software (capas, módulos) | [docs/arquitectura.md](docs/arquitectura.md) |
| Entender el protocolo UCI (framing, comandos, estados) | [docs/protocolo-uci.md](docs/protocolo-uci.md) |
| Ver el plan de implementación por fases | [docs/plan-implementacion.md](docs/plan-implementacion.md) |
| Entender cómo se versiona y publica el proyecto | [docs/versionado.md](docs/versionado.md) |

## Licencia

Uso interno — ver [LICENSE](LICENSE).
