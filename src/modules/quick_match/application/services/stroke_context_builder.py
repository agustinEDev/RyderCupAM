"""
StrokeContextBuilder - Traduce un GolfCourse a lo que necesita el reparto de golpes.

Vive en la capa de aplicacion a proposito: `StrokeAllocationService` es dominio
puro de `quick_match` y no debe conocer las entidades de `golf_course`. Aqui se
hace la traduccion, una sola vez, para los dos consumidores que la necesitan
(el detalle de la partida y el historial de partidas recientes).
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.golf_course.domain.entities.golf_course import GolfCourse

logger = logging.getLogger(__name__)

# Campos por los que ya se ha avisado en este proceso. El detalle de la partida
# se pide cada 10 segundos mientras se juega, asi que avisar en cada llamada
# llenaria el log con la misma linea durante toda la vuelta. Interesa enterarse
# del campo mal valorado, no contarlo 24 veces por minuto.
_reported_courses: set[str] = set()


def _report_once(course_id, message: str, *args) -> None:
    key = str(course_id)
    if key in _reported_courses:
        return
    _reported_courses.add(key)
    logger.warning(message, *args)


@dataclass(frozen=True)
class StrokeContext:
    """Datos del campo ya resueltos para repartir golpes."""

    tee_ratings: dict[tuple[str, str | None], TeeRating]
    holes_by_stroke_index: list[int]
    par_by_hole: dict[int, int]
    # Orden de dificultad propio de cada barra. `golf_course.holes` es solo la
    # tarjeta de la PRIMERA barra (ver `GolfCourse._sync_holes_and_tees`), y el
    # importador de la RFEG guarda una tarjeta por barra: en 56 de los 800
    # campos federados el stroke index cambia de una a otra. Repartir con el
    # orden de otra barra pone los golpes en los hoyos equivocados.
    holes_by_stroke_index_by_tee: dict[tuple[str, str | None], list[int]] = field(
        default_factory=dict
    )

    @property
    def course_par(self) -> int:
        return sum(self.par_by_hole.values())


class StrokeContextBuilder:
    """Construye el StrokeContext de un campo."""

    @staticmethod
    def build(golf_course: GolfCourse) -> StrokeContext:
        """
        Args:
            golf_course: Campo donde se juega la partida

        Returns:
            StrokeContext con los ratings por (color, genero), el orden de hoyos
            por stroke index y el par de cada hoyo.
        """
        holes = sorted(golf_course.holes, key=lambda h: h.number)
        par_by_hole = {hole.number: hole.par for hole in holes}
        course_par = sum(par_by_hole.values())

        if not holes:
            # Sin tarjeta no hay stroke index con el que repartir, asi que la
            # partida acaba jugandose a bruto — que es justo el fallo que este
            # reparto arregla. Degradar en silencio aqui seria indistinguible del
            # exito, y con 800 campos importados conviene poder contarlo.
            _report_once(
                golf_course.id,
                "Golf course %s has no holes: quick match strokes cannot be allocated",
                golf_course.id,
            )

        holes_by_stroke_index = [
            hole.number for hole in sorted(holes, key=lambda h: h.stroke_index)
        ]

        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_tee: dict[tuple[str, str | None], list[int]] = {}
        for tee in golf_course.tees:
            gender = tee.gender.value if tee.gender else None
            if tee.holes:
                holes_by_tee[(tee.color.value, gender)] = [
                    hole.number for hole in sorted(tee.holes, key=lambda h: h.stroke_index)
                ]
            # El par del tee cuando trae tarjeta propia; si no, el del campo.
            par = tee.par_total if tee.holes else course_par
            try:
                rating = TeeRating(
                    course_rating=Decimal(str(tee.course_rating)),
                    slope_rating=tee.slope_rating,
                    par=par,
                )
            except ValueError as exc:
                # Un tee con ratings fuera del rango WHS (dato importado suelto)
                # no debe tumbar la partida entera: se omite y quien juegue desde
                # el cae en el fallback del Handicap Index.
                _report_once(
                    golf_course.id,
                    "Skipping tee %s (%s) of golf course %s: %s. "
                    "Players on it fall back to their Handicap Index.",
                    tee.color.value,
                    gender,
                    golf_course.id,
                    exc,
                )
                continue
            tee_ratings[(tee.color.value, gender)] = rating

        return StrokeContext(
            tee_ratings=tee_ratings,
            holes_by_stroke_index=holes_by_stroke_index,
            par_by_hole=par_by_hole,
            holes_by_stroke_index_by_tee=holes_by_tee,
        )
