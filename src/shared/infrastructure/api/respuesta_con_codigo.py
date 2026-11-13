"""
La respuesta de error con su código y un texto fijo (BE #562).

CodeQL (py/stack-trace-exposure) marca toda respuesta construida con el texto
de una excepción. Aquí el `detail` sale siempre de un diccionario fijo por
código: la excepción solo aporta el código, y la pantalla lo traduce.
"""

from collections.abc import Mapping
from typing import Any, TypeVar

from fastapi.responses import JSONResponse

# Para un código sin texto: nunca el mensaje de la excepción
DETALLE_GENERICO = "No se ha podido completar la operación."

# El código es un str o un StrEnum (los motivos de la ventana): los textos van por él
Codigo = TypeVar("Codigo", bound=str)


def respuesta_con_codigo(
    status_code: int,
    textos: Mapping[Codigo, str],
    codigo: Codigo | None,
    **campos: Any,
) -> JSONResponse:
    """
    Un error con `detail` fijo y `error_code` en la raíz.

    Args:
        status_code: El código HTTP
        textos: El texto fijo de cada código
        codigo: El código del error; elige el texto y es el `error_code`
        **campos: Más campos de la raíz, tras los dos fijos; un `error_code`
            aquí sustituye al código (el de la actualización de hándicaps, con
            el motivo aparte en `reason_code`). Un `detail`, nunca

    Returns:
        La respuesta, sin nada del mensaje de la excepción

    Raises:
        TypeError: Si entre los campos va un `detail`: el texto es el fijo
    """
    if "detail" in campos:
        raise TypeError("respuesta_con_codigo: el `detail` es el texto fijo del código")
    detalle = textos.get(codigo, DETALLE_GENERICO) if codigo is not None else DETALLE_GENERICO
    return JSONResponse(
        status_code=status_code,
        content={"detail": detalle, "error_code": codigo, **campos},
    )
