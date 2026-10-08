"""
El contexto de golpes de un campo, con los avisos de partida rápida (BE #165).

La traducción del campo vive en `golf_course` y es la misma para todos. Aquí
solo se decide qué se avisa, y cuántas veces. Lo usan los dos consumidores de
partida rápida: el detalle de la partida y el historial de partidas recientes.
"""

import logging

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.services.stroke_context import (
    StrokeContext,
    StrokeContextBuilder,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.shared.domain.services.personal_round import personal_playing_handicap

logger = logging.getLogger(__name__)

# Campos por los que ya se ha avisado en este proceso. El detalle de la partida
# se pide cada 10 segundos mientras se juega, así que avisar en cada llamada
# llenaría el log con la misma línea durante toda la vuelta. Interesa enterarse
# del campo mal valorado, no contarlo 24 veces por minuto.
_reported_courses: set[str] = set()


def course_context_for(golf_course: GolfCourse) -> StrokeContext:
    """Contexto del campo, avisando una vez por campo de lo que falla."""
    context = StrokeContextBuilder.build(golf_course)

    key = str(golf_course.id)
    if key in _reported_courses:
        return context

    if not context.holes_by_stroke_index:
        # Sin tarjeta no hay stroke index con el que repartir, así que la
        # partida acaba jugándose a bruto. Degradar en silencio sería
        # indistinguible del éxito, y con 800 campos importados conviene contarlo.
        _reported_courses.add(key)
        logger.warning(
            "Golf course %s has no holes: quick match strokes cannot be allocated",
            golf_course.id,
        )

    for tee in context.unrated_tees:
        _reported_courses.add(key)
        logger.warning(
            "Skipping tee %s (%s) of golf course %s: it cannot be rated "
            "(CR %s, SR %s, par %s). Players on it fall back to their Handicap Index.",
            tee.color,
            tee.gender,
            golf_course.id,
            tee.course_rating,
            tee.slope_rating,
            tee.par,
        )

    return context


def own_playing_handicap(
    match: QuickMatch,
    participant: QuickMatchParticipant,
    handicap_index: float | None,
    golf_course: GolfCourse,
) -> int | None:
    """
    Hándicap de juego del participante en su vuelta propia, contra el campo.

    La pendiente y el rating de su barra, como la partida, o el índice si la
    barra no se puede valorar: `personal_playing_handicap`, la misma pieza que
    usan el historial y las estadísticas para los partidos de torneo. El historial y las estadísticas puntuaban con el índice tal
    cual, sin barra, y la misma vuelta daba 28 puntos en el panel y 32 en la
    partida (BE #513). Al 100 %.

    En match play también: el partido se decide por la diferencia con el rival,
    pero la vuelta de cada uno se mide contra el campo con su propio hándicap.

    Devuelve None sin hándicap conocido, y 0 en una partida scratch (el reparto
    no da golpes). Lo devuelto ya es el hándicap de juego: quien lo use no debe
    volver a pasarlo por la barra ni por el allowance.
    """
    tee_rating = course_context_for(golf_course).rating_for(
        participant.tee_color, participant.tee_gender
    )
    return personal_playing_handicap(handicap_index, tee_rating, scratch=not match.uses_handicap())
