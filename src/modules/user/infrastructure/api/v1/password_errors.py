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
from src.modules.user.domain.value_objects.password import InvalidPasswordError, Password
from src.shared.infrastructure.api.respuesta_con_codigo import respuesta_con_codigo

# El de cada regla, como lo dice el dominio; la longitud, sin lo tecleado. Bandit
# (B105) toma por contraseña el texto de una clave PASSWORD_* o *_TOKEN_*: es un mensaje
_DETALLE: dict[str, str] = {
    "PASSWORD_EMPTY": "La contraseña no puede estar vacía",  # nosec B105 - mensaje
    "PASSWORD_EDGE_SPACES": "La contraseña no puede tener espacios al inicio o final",  # nosec B105 - mensaje
    "PASSWORD_TOO_SHORT": f"La contraseña debe tener al menos {Password.MIN_LENGTH} caracteres",
    "PASSWORD_TOO_LONG": f"La contraseña no puede exceder {Password.MAX_LENGTH} caracteres",
    "PASSWORD_NO_UPPERCASE": "La contraseña debe contener al menos una letra mayúscula (A-Z)",  # nosec B105 - mensaje
    "PASSWORD_NO_LOWERCASE": "La contraseña debe contener al menos una letra minúscula (a-z)",  # nosec B105 - mensaje
    "PASSWORD_NO_DIGIT": "La contraseña debe contener al menos un número (0-9)",  # nosec B105 - mensaje
    "PASSWORD_NO_SYMBOL": (  # nosec B105 - mensaje
        "La contraseña debe contener al menos un carácter especial (!@#$%^&*()_+-=[]{}|;:,.<>?)"
    ),
    "PASSWORD_TOO_COMMON": (  # nosec B105 - mensaje
        "Esta contraseña es demasiado común y fácil de adivinar. Por favor, elige una "
        "contraseña más única"
    ),
    "PASSWORD_REUSED": (  # nosec B105 - mensaje
        "Cannot reuse any of your last 5 passwords. Please choose a different password."
    ),
    "PASSWORD_INVALID": "La contraseña no es válida",  # nosec B105 - mensaje
    "RESET_TOKEN_INVALID": "Token de reseteo inválido o expirado",  # nosec B105 - mensaje
}


def coded_bad_request(error: InvalidPasswordError | InvalidResetTokenError) -> JSONResponse:
    """400 con el motivo y su código: el de la regla de la contraseña o el del token."""
    return respuesta_con_codigo(status.HTTP_400_BAD_REQUEST, _DETALLE, error.error_code)
