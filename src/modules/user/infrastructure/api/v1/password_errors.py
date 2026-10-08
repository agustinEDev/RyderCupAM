"""
La respuesta de una contraseña que rompe la política (BE #519).

Registro, reset y cambio desde el perfil devuelven lo mismo: un 400 con el
motivo en `detail` y el código de la regla en la RAÍZ (`error_code`), donde el
cliente lo lee (`api.js`), como `SCORING_NOT_OPEN_YET`. El texto va en español;
el código es lo que deja al cliente enseñarlo en el idioma del usuario.
"""

from fastapi import status
from fastapi.responses import JSONResponse

from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.value_objects.password import InvalidPasswordError


def password_policy_response(error: InvalidPasswordError) -> JSONResponse:
    """400 con el motivo y el código de la regla que rompe la contraseña."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(error), "error_code": error.code},
    )


def reset_token_response(error: InvalidResetTokenError) -> JSONResponse:
    """400 del token de reseteo inválido, con su código (BE #519): el texto va en español."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(error), "error_code": error.code},
    )
