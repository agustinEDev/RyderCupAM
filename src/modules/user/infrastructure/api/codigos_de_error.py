"""
Errores del módulo user que la API traduce a su código HTTP en un solo sitio.

La respuesta es la que daba cada ruta con su `except X: raise HTTPException(código, str(e))`:
el código de aquí y {"detail": str(e)}. Lo registra la composition root
(`src/config/codigos_de_error.py`). Un error que en alguna ruta da otro código, o un texto
propio, se sigue traduciendo en esa ruta.
"""

from fastapi import status

from src.modules.user.domain.errors.handicap_errors import HandicapNotFoundError
from src.modules.user.domain.errors.user_errors import (
    AliasAlreadyTakenError,
    AvatarUploadNotFoundError,
    AvatarUploadTooLargeError,
    InvalidAvatarImageError,
    TermsAcceptanceRequiredError,
    UserNotFoundError,
)
from src.modules.user.domain.exceptions.user_has_activity_exception import UserHasActivityException

CODIGOS: dict[type[Exception], int] = {
    # 400: la petición no tiene sentido para el estado o las reglas del juego
    InvalidAvatarImageError: status.HTTP_400_BAD_REQUEST,
    # 404: no existe (o no se le deja ver)
    AvatarUploadNotFoundError: status.HTTP_404_NOT_FOUND,
    HandicapNotFoundError: status.HTTP_404_NOT_FOUND,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    # 409: choca con lo que ya hay
    AliasAlreadyTakenError: status.HTTP_409_CONFLICT,
    UserHasActivityException: status.HTTP_409_CONFLICT,
    # 413: la subida pasa del tamaño máximo
    AvatarUploadTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    # 422: datos que no se pueden procesar
    TermsAcceptanceRequiredError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}
