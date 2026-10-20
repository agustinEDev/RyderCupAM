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

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.services.stroke_context import (
    StrokeContext,
    StrokeContextBuilder,
)

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
