"""
El contexto de golpes de un campo, con los avisos de competición (BE #165).

La traducción del campo vive en `golf_course` y es la misma para todos. Aquí
solo se decide qué se avisa: generar partidos es puntual, así que se avisa en
cada generación, y la consecuencia es la de competición. Un jugador inscrito en
una barra sin valorar no puede tener la ronda generada: los llamantes tratan la
barra ausente como `TeeColorNotFoundError`, un 400 con mensaje. En partida
rápida, en cambio, ese jugador juega con su Handicap Index.
"""

import logging

from src.modules.competition.application.exceptions import PendingGameNotRecalculableError
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import (
    StrokeContext,
    StrokeContextBuilder,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

logger = logging.getLogger(__name__)


def course_context_for(golf_course: GolfCourse) -> StrokeContext:
    """Contexto del campo, avisando de las barras que se quedaron fuera."""
    context = StrokeContextBuilder.build(golf_course)

    for color, gender in context.rated_with_course_par:
        # Camino COMÚN —25 de los 800 campos importados cambian de par entre
        # barras—, y tomarlo cambia el course handicap de quien juegue esa barra:
        # se deja rastro, sin llegar a aviso.
        logger.debug(
            "Tee %s (%s) of golf course %s could not be rated against its own par; "
            "using the course par (%s) instead",
            color,
            gender,
            golf_course.id,
            context.course_par,
        )

    for tee in context.unrated_tees:
        logger.warning(
            "Golf course %s has a tee (%s, CR %s, SR %s, par %s) that cannot be rated: "
            "it is left out of the context, and a player enrolled on it will not be able "
            "to have their round generated",
            golf_course.id,
            tee.color,
            tee.course_rating,
            tee.slope_rating,
            tee.par,
        )

    return context


async def contexto_del_campo(
    campos: IGolfCourseRepository,
    golf_course_id: GolfCourseId,
    contextos: dict[GolfCourseId, StrokeContext] | None,
) -> StrokeContext:
    """
    El contexto de un campo, leído una sola vez por ejecución si se pasa una caché
    (BE #912: cambiar unas barras rehace varios partidos del mismo campo).

    Raises:
        PendingGameNotRecalculableError: Si el campo ya no existe
    """
    if contextos is not None and golf_course_id in contextos:
        return contextos[golf_course_id]
    campo = await campos.find_by_id(golf_course_id)
    if campo is None:
        raise PendingGameNotRecalculableError("El campo de una partida pendiente ya no existe")
    contexto = course_context_for(campo)
    if contextos is not None:
        contextos[golf_course_id] = contexto
    return contexto
