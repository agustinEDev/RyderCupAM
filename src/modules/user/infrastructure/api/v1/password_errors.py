"""
La respuesta de una contraseña que rompe la política (BE #519).

Registro, reset y cambio desde el perfil devuelven lo mismo: un 400 con el
motivo en `detail` y el código de la regla en la RAÍZ (`error_code`), donde el
cliente lo lee (`api.js`), como `SCORING_NOT_OPEN_YET`. El texto va en español;
el código es lo que deja al cliente enseñarlo en el idioma del usuario.

El texto es fijo por código, nunca el de la excepción (CodeQL, BE #562).
"""

from fastapi import status
from fastapi.responses import JSONResponse

from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.value_objects.password import (
    MENSAJES_DE_LA_CONTRASENA,
    InvalidPasswordError,
)
from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo

# Los del dominio, sin copiarlos: el de cada regla y el del token
_DETALLE: dict[str, str] = {
    **MENSAJES_DE_LA_CONTRASENA,
    InvalidResetTokenError.error_code: InvalidResetTokenError.MENSAJE,
}


def coded_bad_request(error: InvalidPasswordError | InvalidResetTokenError) -> JSONResponse:
    """400 con el motivo y su código: el de la regla de la contraseña o el del token."""
    return respuesta_con_codigo(status.HTTP_400_BAD_REQUEST, _DETALLE, error.error_code)
