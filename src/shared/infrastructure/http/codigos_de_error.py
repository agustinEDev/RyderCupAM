"""
Traduce errores de dominio a su respuesta HTTP en un solo sitio (fase 5 del plan de calidad).

Cada módulo declara su mapa `excepción -> código` y la composition root los registra con
`registra_los_codigos`. La respuesta es la misma que daba
`raise HTTPException(status_code=código, detail=str(e))` en cada ruta: el código y
`{"detail": str(e)}`. Starlette busca el manejador por la jerarquía de la excepción, así que
una subclase sin código propio recibe el de su clase registrada más cercana.
"""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _responde_con(codigo: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def responde(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=codigo, content={"detail": str(error)})

    return responde


def registra_los_codigos(app: FastAPI, codigos: Mapping[type[Exception], int]) -> None:
    """Registra en la app un manejador por excepción, con el código que le toca."""
    for error, codigo in codigos.items():
        app.add_exception_handler(error, _responde_con(codigo))
