"""
TeeContextBuilder - Traduce un GolfCourse a lo que necesita el reparto de golpes.

`GenerateMatchesUseCase` y `ReassignMatchPlayersUseCase` tenian cada uno su
propia copia de esta traduccion, y las dos arrastraban los mismos dos fallos:
valoraban todas las barras contra el par del campo y repartian los golpes con el
stroke index de la tarjeta de referencia. Una sola fuente evita que el proximo
arreglo se aplique solo en una de las dos.

Equivalente al `StrokeContextBuilder` de `quick_match`, que hace lo mismo para
las partidas rapidas.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.golf_course.domain.entities.golf_course import GolfCourse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeeContext:
    """Ratings y orden de dificultad de un campo, listos para repartir golpes."""

    tee_ratings: dict[tuple[str, str | None], TeeRating]
    holes_by_stroke_index: list[int]
    # Orden propio de cada barra. `golf_course.reference_card` es solo la tarjeta de la
    # PRIMERA barra (ver `GolfCourse._sync_holes_and_tees`), y el importador de
    # la RFEG guarda una por barra: de los 800 campos federados con mas de una
    # barra con tarjeta, 56 tienen stroke index distinto entre ellas y 25 par
    # distinto. Repartir con el orden de otra barra pone los golpes en los hoyos
    # equivocados.
    holes_by_tee: dict[tuple[str, str | None], list[int]] = field(default_factory=dict)

    def holes_for(self, tee_color, tee_gender) -> list[int]:
        """
        Orden de dificultad de una barra concreta.

        Cae al del campo cuando la barra no trae tarjeta propia. Misma reserva de
        genero que la busqueda de ratings, para que las dos resuelvan la misma
        barra.
        """
        if tee_color is None:
            return self.holes_by_stroke_index
        color = tee_color.value
        gender = tee_gender.value if tee_gender else None
        return (
            self.holes_by_tee.get((color, gender))
            or self.holes_by_tee.get((color, None))
            or self.holes_by_stroke_index
        )


class TeeContextBuilder:
    """Construye el TeeContext de un campo."""

    @staticmethod
    def build(golf_course: GolfCourse) -> TeeContext:
        course_par = sum(h.par for h in golf_course.reference_card)
        holes_by_stroke_index = [
            h.number for h in sorted(golf_course.reference_card, key=lambda h: h.stroke_index)
        ]

        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_tee: dict[tuple[str, str | None], list[int]] = {}

        for tee in golf_course.tees:
            gender = tee.gender.value if tee.gender else None
            tee_key = (tee.color.value, gender)
            tee_ratings[tee_key] = TeeContextBuilder._rating_for(tee, course_par, golf_course)

            card = TeeContextBuilder._card_for(tee)
            if card:
                holes_by_tee[tee_key] = card

        return TeeContext(
            tee_ratings=tee_ratings,
            holes_by_stroke_index=holes_by_stroke_index,
            holes_by_tee=holes_by_tee,
        )

    @staticmethod
    def _rating_for(tee, course_par: int, golf_course: GolfCourse) -> TeeRating:
        """
        Valoracion de una barra, contra SU par cuando trae tarjeta propia.

        Si ese par no sirve —se sale del rango WHS, o la tarjeta viene
        malformada— se cae al del campo, que es lo que se venia usando, en vez de
        dejar la ronda sin poder generar partidos.
        """
        course_rating = Decimal(str(tee.course_rating))
        try:
            return TeeRating(
                course_rating=course_rating,
                slope_rating=tee.slope_rating,
                par=tee.par_total if tee.holes else course_par,
            )
        except (ValueError, TypeError):
            logger.debug(
                "Tee %s of golf course %s has an unusable par; rating it against the course par",
                tee.color.value,
                golf_course.id,
            )
            return TeeRating(
                course_rating=course_rating,
                slope_rating=tee.slope_rating,
                par=course_par,
            )

    @staticmethod
    def _card_for(tee) -> list[int]:
        """Hoyos de la barra ordenados por su stroke index; vacio si no tiene tarjeta."""
        if not tee.holes:
            return []
        try:
            return [h.number for h in sorted(tee.holes, key=lambda h: h.stroke_index)]
        except TypeError:
            # Tarjeta malformada: se reparte con el orden del campo
            return []
