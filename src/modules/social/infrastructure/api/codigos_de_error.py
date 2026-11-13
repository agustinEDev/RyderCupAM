"""
Errores del módulo social que la API traduce a su código HTTP en un solo sitio.

La respuesta es la que daba cada ruta con su `except X: raise HTTPException(código, str(e))`:
el código de aquí y {"detail": str(e)}. Lo registra la composition root
(`src/config/codigos_de_error.py`). Un error que en alguna ruta da otro código, o un texto
propio, se sigue traduciendo en esa ruta.
"""

from fastapi import status

from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    AddresseeNotFoundError,
    FriendshipNotFoundError,
    GamesTogetherNotVisibleError,
    NotAddresseeError,
    NotFriendshipParticipantError,
    PhotoNotFoundError,
    ProfileGalleryFullError,
)
from src.modules.social.domain.exceptions.social_violations import (
    BlockedUserViolation,
    DuplicateFriendRequestViolation,
    DuplicateFriendshipViolation,
    InvalidFriendshipStatusViolation,
    SelfFriendRequestViolation,
)

CODIGOS: dict[type[Exception], int] = {
    # 400: la petición no tiene sentido para el estado o las reglas del juego
    SelfFriendRequestViolation: status.HTTP_400_BAD_REQUEST,
    # 403: quien pide no puede hacerlo
    ActivityNotVisibleError: status.HTTP_403_FORBIDDEN,
    BlockedUserViolation: status.HTTP_403_FORBIDDEN,
    GamesTogetherNotVisibleError: status.HTTP_403_FORBIDDEN,
    NotAddresseeError: status.HTTP_403_FORBIDDEN,
    NotFriendshipParticipantError: status.HTTP_403_FORBIDDEN,
    # 404: no existe (o no se le deja ver)
    AddresseeNotFoundError: status.HTTP_404_NOT_FOUND,
    FriendshipNotFoundError: status.HTTP_404_NOT_FOUND,
    PhotoNotFoundError: status.HTTP_404_NOT_FOUND,
    # 409: choca con lo que ya hay
    DuplicateFriendRequestViolation: status.HTTP_409_CONFLICT,
    # La UoW traduce así el choque con uq_friendship_pair; si un caso de uso no
    # lo recoge, es otra petición que ganó la carrera, no un error del servidor
    DuplicateFriendshipViolation: status.HTTP_409_CONFLICT,
    InvalidFriendshipStatusViolation: status.HTTP_409_CONFLICT,
    ProfileGalleryFullError: status.HTTP_409_CONFLICT,
}
