"""
Lo que no deja cambiar unas barras, con su código HTTP y un texto fijo por código, no
el de la excepción (CodeQL). Lo comparten los cambios de barras de las inscripciones
y de los campos de la competición (#912, barras por campo).
"""

from fastapi import status
from fastapi.responses import JSONResponse

from src.modules.competition.application.exceptions import (
    CourseNotInCompetitionError,
    PendingGameNotRecalculableError,
)
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    EnrollmentNotApprovedError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)

ERRORES_DE_BARRAS: tuple[type[Exception], ...] = (
    TeeNotAvailableError,
    TeeChangeClosedError,
    PendingGameNotRecalculableError,
    EnrollmentNotApprovedError,
    CourseNotInCompetitionError,
)

_NO_SE_CAMBIAN: dict[str, tuple[int, str]] = {
    TeeNotAvailableError.error_code: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "That tee is not rated for this player on the courses still to be played.",
    ),
    TeeChangeClosedError.error_code: (
        status.HTTP_409_CONFLICT,
        "The competition has already finished or was cancelled.",
    ),
    PendingGameNotRecalculableError.error_code: (
        status.HTTP_409_CONFLICT,
        "A game still to be played cannot be recalculated with the new tee.",
    ),
    EnrollmentNotApprovedError.error_code: (
        status.HTTP_409_CONFLICT,
        "Only an approved enrollment can change its tee.",
    ),
    CourseNotInCompetitionError.error_code: (
        status.HTTP_404_NOT_FOUND,
        "That course is not one of this competition.",
    ),
}


def respuesta_de_barras(error: Exception) -> JSONResponse:
    """La respuesta de uno de `ERRORES_DE_BARRAS`: su código, su `error_code` y su texto."""
    error_code: str = getattr(error, "error_code")  # noqa: B009 - todos lo llevan
    codigo, texto = _NO_SE_CAMBIAN[error_code]
    return JSONResponse(status_code=codigo, content={"detail": texto, "error_code": error_code})
