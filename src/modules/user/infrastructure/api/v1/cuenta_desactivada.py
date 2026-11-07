"""
La respuesta a una cuenta desactivada, la misma en todos los caminos (#750 punto 1).

403 con `error_code: ACCOUNT_DEACTIVATED`: la app lo dice en su idioma. Antes solo la
daba Google; el login con contraseña y la verificación del correo daban el texto en
inglés del backend.
"""

from fastapi import status
from fastapi.responses import JSONResponse

from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo

ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
TEXTO = "This account has been deactivated. Contact an administrator."


def respuesta_de_cuenta_desactivada() -> JSONResponse:
    """El 403 con su código y el texto de siempre."""
    return respuesta_con_codigo(
        status.HTTP_403_FORBIDDEN, {ACCOUNT_DEACTIVATED: TEXTO}, ACCOUNT_DEACTIVATED
    )
