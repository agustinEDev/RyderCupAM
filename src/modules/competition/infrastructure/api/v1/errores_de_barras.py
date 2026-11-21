"""
Lo que no deja cambiar unas barras, con su código HTTP y un texto fijo por código, no
el de la excepción (CodeQL). Lo comparten los cambios de barras de las inscripciones
y de los campos de la competición (#912, barras por campo).
"""

from fastapi import status
from fastapi.responses import JSONResponse

from src.modules.competition.application.exceptions import (
    CourseNotInCompetitionError,
    CourseTeeNotAvailableError,
    EnrollmentNotApprovedError,
    PendingGameNotRecalculableError,
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

# Por clase, de la más concreta a la más general: la del campo para un género lleva
# el mismo código que la del jugador, pero su propio texto
_NO_SE_CAMBIAN: dict[type[Exception], tuple[int, str]] = {
    CourseTeeNotAvailableError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "That tee is not available for this gender on this course.",
    ),
    TeeNotAvailableError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "That tee is not rated for this player on the courses still to be played.",
    ),
    TeeChangeClosedError: (
        status.HTTP_409_CONFLICT,
        "The competition has already finished or was cancelled.",
    ),
    PendingGameNotRecalculableError: (
        status.HTTP_409_CONFLICT,
        "A game still to be played cannot be recalculated with the new tee.",
    ),
    EnrollmentNotApprovedError: (
        status.HTTP_409_CONFLICT,
        "Only an approved enrollment can change its tee.",
    ),
    CourseNotInCompetitionError: (
        status.HTTP_404_NOT_FOUND,
        "That course is not one of this competition.",
    ),
}


def respuesta_de_barras(error: Exception) -> JSONResponse:
    """La respuesta de uno de `ERRORES_DE_BARRAS`: su código, su `error_code` y su texto."""
    clase = next(c for c in type(error).__mro__ if c in _NO_SE_CAMBIAN)
    codigo, texto = _NO_SE_CAMBIAN[clase]
    error_code: str = getattr(error, "error_code")  # noqa: B009 - todos lo llevan
    return JSONResponse(status_code=codigo, content={"detail": texto, "error_code": error_code})
