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
            # La barra que no se puede valorar se queda FUERA del diccionario en
            # vez de tumbar la construccion entera: quien la juegue jugara con su
            # Handicap Index, y el resto del campo sigue funcionando. Ver #219.
            rating = TeeContextBuilder._rating_for(tee, course_par, golf_course)
            if rating is not None:
                tee_ratings[tee_key] = rating

            card = TeeContextBuilder._card_for(tee)
            if card:
                holes_by_tee[tee_key] = card

        return TeeContext(
            tee_ratings=tee_ratings,
            holes_by_stroke_index=holes_by_stroke_index,
            holes_by_tee=holes_by_tee,
        )

    @staticmethod
    def _rating_for(tee, course_par: int, golf_course: GolfCourse) -> TeeRating | None:
        """
        Valoracion de una barra, contra SU par cuando trae tarjeta propia.

        Si ese par no sirve —se sale del rango, o la tarjeta viene malformada—
        se cae al del campo, que es lo que se venia usando.

        Y si con el par del campo tampoco vale, devuelve None: la barra se queda
        fuera del contexto y quien la juegue jugara con su Handicap Index, igual
        que en partida rapida. Antes ese segundo intento repetia el mismo
        `course_rating` y el mismo `slope_rating`, asi que cuando lo que se salia
        de rango era el rating y no el par, la reserva lanzaba igual que el
        primer intento: el ValueError subia hasta la API y la ronda se quedaba
        sin poder generar partidos —justo lo que esta reserva existe para
        evitar—. Ver RyderCupAm#219.
        """
        course_rating = Decimal(str(tee.course_rating))
        try:
            return TeeRating(
                course_rating=course_rating,
                slope_rating=tee.slope_rating,
                par=tee.par_total if tee.holes else course_par,
            )
        except (ValueError, TypeError):
            pass

        try:
            return TeeRating(
                course_rating=course_rating,
                slope_rating=tee.slope_rating,
                par=course_par,
            )
        except (ValueError, TypeError):
            # Aviso, no debug: generar partidos es puntual —no como el detalle
            # de una partida rapida, que se pide cada 10 segundos— y con 800
            # campos importados interesa saber cual se quedo sin valorar.
            logger.warning(
                "Golf course %s has a tee (%s) that cannot be rated: "
                "its players will play off their Handicap Index",
                golf_course.id,
                tee.color.value,
            )
            return None

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
