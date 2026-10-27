"""El 403 de lo jugado de una privada, igual en todas sus rutas (tabla del 27 oct 2026)."""

from collections.abc import Awaitable

from fastapi import status
from fastapi.responses import JSONResponse

from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    NoPuedeVerloError,
)

# El código va en la raíz del cuerpo, donde lo lee el cliente (`api.js`)
SOLO_QUIEN_PARTICIPA = {
    "detail": "Lo jugado de una competición privada solo lo ven quienes participan.",
    "error_code": "PRIVATE_COMPETITION",
}


async def cerrada(exigir: Awaitable[None]) -> JSONResponse | None:
    """El 403 si la puerta no le deja pasar; None si puede verlo."""
    try:
        await exigir
    except NoPuedeVerloError:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=SOLO_QUIEN_PARTICIPA)
    return None
