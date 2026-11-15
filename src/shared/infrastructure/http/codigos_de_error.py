"""
Traduce errores de dominio a su respuesta HTTP en un solo sitio (fase 5 del plan de calidad).

Cada módulo declara su mapa `excepción -> código` y la composition root los registra con
`registra_los_codigos`. La respuesta es la misma que daba
`raise HTTPException(status_code=código, detail=str(e))` en cada ruta: el código y
`{"detail": str(e)}`. Starlette busca el manejador por la jerarquía de la excepción, así que
una subclase sin código propio recibe el de su clase registrada más cercana.

Las que se digan llevan además su `error_code` en la raíz, como el resto de códigos que lee
el frontend (el plazo de inscripción, 15 nov 2026). Se dice una a una: otras del mapa ya
traen `error_code` y su respuesta no debe cambiar sin que nadie lo decida.
"""

from collections.abc import Awaitable, Callable, Collection, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _responde_con(
    codigo: int, con_su_codigo: bool
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def responde(_request: Request, error: Exception) -> JSONResponse:
        contenido: dict[str, str] = {"detail": str(error)}
        error_code = getattr(error, "error_code", None)
        if con_su_codigo and isinstance(error_code, str):
            contenido["error_code"] = error_code
        return JSONResponse(status_code=codigo, content=contenido)

    return responde


def registra_los_codigos(
    app: FastAPI,
    codigos: Mapping[type[Exception], int],
    con_su_codigo: Collection[type[Exception]] = (),
) -> None:
    """
    Registra en la app un manejador por excepción, con el código que le toca; las de
    `con_su_codigo`, con su `error_code` también.
    """
    for error, codigo in codigos.items():
        app.add_exception_handler(error, _responde_con(codigo, error in con_su_codigo))
