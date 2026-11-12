"""
Errores del módulo quick_match que la API traduce a su código HTTP en un solo sitio.

La respuesta es la que daba cada ruta con su `except X: raise HTTPException(código, str(e))`:
el código de aquí y {"detail": str(e)}. Lo registra la composition root
(`src/config/codigos_de_error.py`). Un error que en alguna ruta da otro código, o un texto
propio, se sigue traduciendo en esa ruta.
"""

from fastapi import status

from src.modules.quick_match.application.exceptions import (
    FriendUserNotFoundError,
    GolfCourseNotFoundError,
    InvalidParticipantError,
    InvalidTeeSelectionError,
    NotAScorerError,
    NotAuthorizedToRemoveError,
    NotFriendsError,
    NotQuickMatchCreatorError,
    NotQuickMatchParticipantError,
    QuickMatchIdTakenError,
    QuickMatchNotFoundError,
    QuickMatchNotSharedError,
    TargetParticipantNotFoundError,
)
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    CreatorCannotBeRemovedViolation,
    DuplicateParticipantViolation,
    IncompleteRosterViolation,
    InvalidAllowanceViolation,
    InvalidHoleScoreViolation,
    InvalidQuickMatchStatusViolation,
    InvalidScorerConfigurationViolation,
    InvalidTeamAssignmentViolation,
    NotAssignedScorerViolation,
    NotQuickMatchParticipantViolation,
    QuickMatchFullViolation,
)

CODIGOS: dict[type[Exception], int] = {
    # 400: la petición no tiene sentido para el estado o las reglas del juego
    CreatorCannotBeRemovedViolation: status.HTTP_400_BAD_REQUEST,
    InvalidHoleScoreViolation: status.HTTP_400_BAD_REQUEST,
    # 403: quien pide no puede hacerlo
    NotAScorerError: status.HTTP_403_FORBIDDEN,
    NotAssignedScorerViolation: status.HTTP_403_FORBIDDEN,
    NotAuthorizedToRemoveError: status.HTTP_403_FORBIDDEN,
    NotFriendsError: status.HTTP_403_FORBIDDEN,
    NotQuickMatchCreatorError: status.HTTP_403_FORBIDDEN,
    NotQuickMatchParticipantError: status.HTTP_403_FORBIDDEN,
    QuickMatchNotSharedError: status.HTTP_403_FORBIDDEN,
    # 404: no existe (o no se le deja ver)
    FriendUserNotFoundError: status.HTTP_404_NOT_FOUND,
    GolfCourseNotFoundError: status.HTTP_404_NOT_FOUND,
    NotQuickMatchParticipantViolation: status.HTTP_404_NOT_FOUND,
    QuickMatchNotFoundError: status.HTTP_404_NOT_FOUND,
    TargetParticipantNotFoundError: status.HTTP_404_NOT_FOUND,
    # 409: choca con lo que ya hay
    DuplicateParticipantViolation: status.HTTP_409_CONFLICT,
    InvalidQuickMatchStatusViolation: status.HTTP_409_CONFLICT,
    QuickMatchIdTakenError: status.HTTP_409_CONFLICT,
    # 422: datos que no se pueden procesar
    IncompleteRosterViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidAllowanceViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidParticipantError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidScorerConfigurationViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidTeamAssignmentViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidTeeSelectionError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    QuickMatchFullViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
}
