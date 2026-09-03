"""Codec TVS (Tag-Value-Size) para el bloque de parametros de `SESSION_SET_APP_CONFIG`.

Formato confirmado contra `SDK/Tools/uwb-qorvo-tools/lib/uwb-uci/uci/core.py`
(funcion `tvs_to_bytes`) y `fira_app.py` (tabla de longitudes `App.defs`),
release `QM33SDK-1.1.1`:

    count (1 byte) -- cantidad de parametros
    por cada parametro:
        tag (1 byte)
        longitud en bytes del valor (1 byte)
        valor (longitud bytes, little-endian; si es una lista, cada elemento
               ocupa el mismo ancho fijo del parametro y la longitud
               declarada es el total en bytes, no la cantidad de elementos)

Este bloque va despues del `session_handle` (4 bytes LE) en el payload
completo del Command -- eso lo arma `core/client.py`, no este modulo (modulo
puro, sin I/O, ver docs/arquitectura.md Seccion 3.2).

Solo se soportan los parametros de `AppConfigParam` (alcance minimo, ver
docs/protocolo-uci.md) -- no es un codec TVS generico como el de la fuente.
Decodificar la Response (que no tiene un formato fijo: depende del `Status`)
es responsabilidad de `core/models.py`, no de este modulo.
"""

from __future__ import annotations

from collections.abc import Sequence

from dwm3001c_uci.uci.enums import AppConfigParam

PARAM_WIDTH_BYTES: dict[int, int] = {
    AppConfigParam.DEVICE_TYPE: 1,
    AppConfigParam.RANGING_ROUND_USAGE: 1,
    AppConfigParam.STS_CONFIG: 1,
    AppConfigParam.MULTI_NODE_MODE: 1,
    AppConfigParam.CHANNEL_NUMBER: 1,
    AppConfigParam.DEVICE_MAC_ADDRESS: 2,
    AppConfigParam.DST_MAC_ADDRESS: 2,
    AppConfigParam.SLOT_DURATION: 2,
    AppConfigParam.RANGING_INTERVAL: 4,
    AppConfigParam.DEVICE_ROLE: 1,
    AppConfigParam.RFRAME_CONFIG: 1,
    AppConfigParam.PREAMBLE_CODE_INDEX: 1,
    AppConfigParam.SFD_ID: 1,
    AppConfigParam.SLOTS_PER_RR: 1,
    AppConfigParam.SCHEDULE_MODE: 1,
    AppConfigParam.VENDOR_ID: 2,
    AppConfigParam.STATIC_STS_IV: 6,
}

AppConfigValue = int | Sequence[int]


def encode_app_config(params: Sequence[tuple[int, AppConfigValue]]) -> bytes:
    """Codifica una lista `(tag, valor)` al bloque TVS de `SET_APP_CONFIG`.

    `valor` es un `int` para la mayoria de los parametros, o una secuencia de
    `int` para los que son listas (p. ej. `DST_MAC_ADDRESS` con mas de un
    controlee).
    """
    blob = bytes([len(params)])
    for tag, value in params:
        try:
            width = PARAM_WIDTH_BYTES[tag]
        except KeyError as exc:
            raise ValueError(
                f"parametro AppConfig no soportado por este codec: 0x{tag:02X}"
            ) from exc

        if isinstance(value, int):
            blob += bytes([tag, width]) + value.to_bytes(width, "little")
        else:
            items = list(value)
            blob += bytes([tag, len(items) * width])
            for item in items:
                blob += item.to_bytes(width, "little")

    return blob
