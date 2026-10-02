"""
StrokeContext - Lo que el reparto de golpes necesita saber de un campo (BE #165).

Una sola traducción del campo para competición, partida rápida y estadísticas.
Antes había tres: `TeeContextBuilder` (competición), `StrokeContextBuilder`
(partida rápida) y la valoración de barras de las estadísticas, y no hacían lo
mismo. Decidido el 2 oct 2026: todas con la conducta de competición, que es la
más robusta.

La pieza no avisa de nada: devuelve qué barras se quedaron sin valorar y cuáles
se valoraron con el par del campo, y cada módulo avisa con su mensaje y su
frecuencia. No es lo mismo en competición (la ronda no se puede generar) que en
partida rápida (se juega con el Handicap Index, y el detalle se pide cada 10 s).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.services.tee_lookup import TeeKey, find_tee
from src.shared.domain.value_objects.gender import Gender


def holes_for_tee(
    holes_by_tee: Mapping[TeeKey, list[int]] | None,
    tee_color: TeeColor | None,
    tee_gender: Gender | None,
    default: list[int],
) -> list[int]:
    """
    Orden de dificultad de una barra: el suyo, el de la barra sin género de ese
    color, o `default` (el del campo) si no hay ninguno.
    """
    if tee_color is None or not holes_by_tee:
        return default
    gender = tee_gender.value if tee_gender else None
    return find_tee(holes_by_tee, tee_color.value, gender, default=default)


@dataclass(frozen=True)
class UnratedTee:
    """Barra que se quedó fuera porque sus ratings no caben en los del WHS."""

    color: str
    gender: str | None
    course_rating: Decimal
    slope_rating: int
    par: int


@dataclass(frozen=True)
class StrokeContext:
    """Ratings, orden de dificultad y pares de un campo, listos para repartir."""

    tee_ratings: dict[TeeKey, TeeRating]
    holes_by_stroke_index: list[int]
    par_by_hole: dict[int, int]
    # Orden propio de cada barra. `golf_course.reference_card` es solo la tarjeta
    # de la PRIMERA barra (ver `GolfCourse._sync_holes_and_tees`), y el
    # importador de la RFEG guarda una por barra: de los 800 campos federados con
    # más de una barra con tarjeta, 56 tienen stroke index distinto entre ellas y
    # 25 par distinto. Repartir con el orden de otra barra pone los golpes en los
    # hoyos equivocados.
    holes_by_tee: dict[TeeKey, list[int]] = field(default_factory=dict)
    unrated_tees: tuple[UnratedTee, ...] = ()
    rated_with_course_par: tuple[TeeKey, ...] = ()

    @property
    def course_par(self) -> int:
        return sum(self.par_by_hole.values())

    def holes_for(self, tee_color: TeeColor | None, tee_gender: Gender | None) -> list[int]:
        """Orden de dificultad de una barra; el del campo si no trae tarjeta."""
        return holes_for_tee(self.holes_by_tee, tee_color, tee_gender, self.holes_by_stroke_index)

    def rating_for(self, tee_color: TeeColor | None, tee_gender: Gender | None) -> TeeRating | None:
        """
        Valoración de la barra que juega el jugador, con la misma reserva sin
        género que el orden; None si esa barra no se puede valorar.
        """
        if tee_color is None:
            return None
        gender = tee_gender.value if tee_gender else None
        return find_tee(self.tee_ratings, tee_color.value, gender)


class StrokeContextBuilder:
    """Construye el StrokeContext de un campo."""

    @staticmethod
    def build(golf_course: GolfCourse) -> StrokeContext:
        card = sorted(golf_course.reference_card, key=lambda h: h.number)
        par_by_hole = {hole.number: hole.par for hole in card}
        course_par = sum(par_by_hole.values())
        holes_by_stroke_index = [h.number for h in sorted(card, key=lambda h: h.stroke_index)]

        tee_ratings: dict[TeeKey, TeeRating] = {}
        holes_by_tee: dict[TeeKey, list[int]] = {}
        unrated: list[UnratedTee] = []
        with_course_par: list[TeeKey] = []

        # Se indexa por (color, género) dentro del bucle: una barra repetida
        # sobrescribe a la anterior, y gana la última. Es la misma que resuelve
        # `GolfCourse.tee_for` (#190).
        for tee in golf_course.tees:
            key: TeeKey = (tee.color.value, tee.gender.value if tee.gender else None)
            own_par = tee.par_total if tee.holes else course_par

            rating = _rating(tee, own_par)
            # Se reintenta solo si el par del campo es OTRO: con el mismo par el
            # segundo intento sería idéntico, y lo que falla entonces es el
            # rating, no el par (RyderCupAm#219).
            if rating is None and own_par != course_par:
                rating = _rating(tee, course_par)
                if rating is not None:
                    with_course_par.append(key)

            if rating is not None:
                tee_ratings[key] = rating
            else:
                # Con dos salidas repetidas (#190) manda la última, que es la
                # que da la tarjeta (`GolfCourse.hole_card_for`). Si ella no se
                # puede valorar, la valoración de la anterior no vale: los
                # golpes saldrían de una barra y la tarjeta de otra. Decidido
                # el 2 oct 2026.
                tee_ratings.pop(key, None)
                # Fuera del contexto en vez de tumbar la construcción entera:
                # el resto del campo sigue sirviendo.
                unrated.append(
                    UnratedTee(
                        color=key[0],
                        gender=key[1],
                        course_rating=Decimal(str(tee.course_rating)),
                        slope_rating=tee.slope_rating,
                        par=own_par,
                    )
                )

            tee_card = _card_for(tee)
            if tee_card:
                holes_by_tee[key] = tee_card
            else:
                # Misma regla que con la valoración: si la última de dos salidas
                # repetidas no trae tarjeta válida, la de la anterior no vale y
                # se cae al orden del campo, como `GolfCourse.hole_card_for`.
                holes_by_tee.pop(key, None)

        return StrokeContext(
            tee_ratings=tee_ratings,
            holes_by_stroke_index=holes_by_stroke_index,
            par_by_hole=par_by_hole,
            holes_by_tee=holes_by_tee,
            unrated_tees=tuple(unrated),
            rated_with_course_par=tuple(with_course_par),
        )


def _rating(tee: Tee, par: int) -> TeeRating | None:
    try:
        return TeeRating(
            course_rating=Decimal(str(tee.course_rating)),
            slope_rating=tee.slope_rating,
            par=par,
        )
    except (ValueError, TypeError):
        return None


def _card_for(tee: Tee) -> list[int]:
    """Hoyos de la barra por su stroke index; vacío si no tiene tarjeta."""
    if not tee.holes:
        return []
    try:
        return [h.number for h in sorted(tee.holes, key=lambda h: h.stroke_index)]
    except TypeError:
        # Tarjeta malformada: se reparte con el orden del campo
        return []
