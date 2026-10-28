"""El 403 de lo jugado de una privada, igual en todas sus rutas (tabla del 27 oct 2026)."""

from fastapi import status
from fastapi.responses import JSONResponse

# El código va en la raíz del cuerpo, donde lo lee el cliente (`api.js`)
SOLO_QUIEN_PARTICIPA = {
    "detail": "Lo jugado de una competición privada solo lo ven quienes participan.",
    "error_code": "PRIVATE_COMPETITION",
}


def solo_quien_participa() -> JSONResponse:
    """El 403 de lo jugado de una privada en la que no está."""
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=SOLO_QUIEN_PARTICIPA)
