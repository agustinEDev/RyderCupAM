"""
Desglose de golpes: dónde gana y dónde pierde un jugador (BE #168).

Las métricas que ya existían dicen *cuánto* juega de bien —media respecto al par,
diferencial, índice estimado—. Estas dicen **dónde**, que es lo accionable: si
los golpes se van en los par 3, o en los segundos nueve, o en un campo concreto.

No lee nada nuevo. Trabaja sobre los hoyos que ya se guardan, reducidos antes a
`HoleOutcome` por quien conoce las reglas del WHS.
"""

from dataclasses import dataclass, field

from src.shared.domain.services.countable_round import HALF_ROUND_HOLES
from src.shared.domain.value_objects.hole_outcome import HoleOutcome

# Un hoyo cae en una de estas cuatro cestas según lo que se hizo respecto al par.
# Cuatro y no siete: separar el eagle del albatros da categorías que un amateur
# no llena nunca, y una distribución con ceros no dice nada.
BIRDIE_OR_BETTER = "birdie_or_better"
PAR = "par"
BOGEY = "bogey"
DOUBLE_OR_WORSE = "double_or_worse"

# La ida son los nueve primeros; el resto, la vuelta. Un campo de 9 hoyos jugado
# dos veces sigue numerando 1-18 en la tarjeta, así que la regla vale igual.
FRONT_NINE_LAST_HOLE = HALF_ROUND_HOLES

_ROUND_HOLES = 18


@dataclass(frozen=True)
class RoundOutcome:
    """Una vuelta computable, con el campo donde se jugó y sus hoyos."""

    golf_course_id: str | None
    golf_course_name: str | None
    holes: list[HoleOutcome]


@dataclass(frozen=True)
class Distribution:
    """Cuántos hoyos cayeron en cada cesta, y el total sobre el que se reparten."""

    birdie_or_better: int = 0
    par: int = 0
    bogey: int = 0
    double_or_worse: int = 0
    holes: int = 0


@dataclass(frozen=True)
class ParPerformance:
    """Rendimiento en los hoyos de un par concreto."""

    par: int
    holes: int
    average_to_par: float


@dataclass(frozen=True)
class NinePerformance:
    """Rendimiento en una mitad de la vuelta."""

    holes: int
    average_to_par: float


@dataclass(frozen=True)
class CoursePerformance:
    """Media de un jugador en un campo, en la escala de una vuelta de 18."""

    golf_course_id: str
    golf_course_name: str | None
    rounds: int
    average_to_par: float


@dataclass(frozen=True)
class ScoringBreakdown:
    """El desglose completo. Todo vacío o a None cuando no hay vueltas."""

    holes_counted: int = 0
    rounds_counted: int = 0
    gross_distribution: Distribution = field(default_factory=Distribution)
    net_distribution: Distribution = field(default_factory=Distribution)
    by_par: list[ParPerformance] = field(default_factory=list)
    front_nine: NinePerformance | None = None
    back_nine: NinePerformance | None = None
    by_course: list[CoursePerformance] = field(default_factory=list)


class ScoringBreakdownCalculator:
    """
    Agrega hoyos ya computados en las cuatro vistas del desglose.

    Las medias por par y por mitad van **por hoyo**, no por vuelta: un par 3 no
    se escala a 18 hoyos sin decir un disparate, y así media vuelta y vuelta
    entera hablan en la misma unidad sin corregir nada.

    La media por campo sí va **por vuelta de 18**, porque es la que se compara
    con `scoring_avg`, que ya se publica en esa escala.
    """

    def compute(self, rounds: list[RoundOutcome]) -> ScoringBreakdown:
        holes = [hole for round_ in rounds for hole in round_.holes]
        if not holes:
            return ScoringBreakdown()

        return ScoringBreakdown(
            holes_counted=len(holes),
            # Solo las que aportan hoyos: una vuelta vacía no es una vuelta
            # jugada, y `by_par` y `by_course` ya la ignoran
            rounds_counted=sum(1 for round_ in rounds if round_.holes),
            gross_distribution=self._distribution(hole.gross_to_par for hole in holes),
            net_distribution=self._distribution(hole.net_to_par for hole in holes),
            by_par=self._by_par(holes),
            front_nine=self._nine(
                [hole for hole in holes if hole.number <= FRONT_NINE_LAST_HOLE]
            ),
            back_nine=self._nine(
                [hole for hole in holes if hole.number > FRONT_NINE_LAST_HOLE]
            ),
            by_course=self._by_course(rounds),
        )

    @staticmethod
    def _distribution(to_par_values) -> Distribution:
        cestas = {BIRDIE_OR_BETTER: 0, PAR: 0, BOGEY: 0, DOUBLE_OR_WORSE: 0}
        total = 0
        for to_par in to_par_values:
            total += 1
            if to_par <= -1:
                cestas[BIRDIE_OR_BETTER] += 1
            elif to_par == 0:
                cestas[PAR] += 1
            elif to_par == 1:
                cestas[BOGEY] += 1
            else:
                cestas[DOUBLE_OR_WORSE] += 1

        return Distribution(
            birdie_or_better=cestas[BIRDIE_OR_BETTER],
            par=cestas[PAR],
            bogey=cestas[BOGEY],
            double_or_worse=cestas[DOUBLE_OR_WORSE],
            holes=total,
        )

    @classmethod
    def _by_par(cls, holes: list[HoleOutcome]) -> list[ParPerformance]:
        """
        Una entrada por cada par que aparezca de verdad, no una lista fija de
        3-4-5: hay campos con hoyos par 6 —La Marquesa tiene uno— y un pitch &
        putt es todo par 3. Fijar las categorías escondería los primeros y
        llenaría de vacíos los segundos.
        """
        por_par: dict[int, list[int]] = {}
        for hole in holes:
            por_par.setdefault(hole.par, []).append(hole.net_to_par)

        return [
            ParPerformance(par=par, holes=len(valores), average_to_par=cls._average(valores))
            for par, valores in sorted(por_par.items())
        ]

    @classmethod
    def _nine(cls, holes: list[HoleOutcome]) -> NinePerformance | None:
        """None sin hoyos: quien solo juega la ida no tiene una vuelta mala."""
        if not holes:
            return None
        return NinePerformance(
            holes=len(holes),
            average_to_par=cls._average([hole.net_to_par for hole in holes]),
        )

    @classmethod
    def _by_course(cls, rounds: list[RoundOutcome]) -> list[CoursePerformance]:
        """
        Media por campo, ordenada de mejor a peor.

        Las vueltas sin campo conocido se quedan fuera en vez de agruparse bajo
        un campo inventado: no se pueden comparar con nada.
        """
        por_campo: dict[str, tuple[str | None, list[float]]] = {}
        for round_ in rounds:
            if round_.golf_course_id is None or not round_.holes:
                continue
            _, vueltas = por_campo.setdefault(
                round_.golf_course_id, (round_.golf_course_name, [])
            )
            vueltas.append(cls._round_to_par_over_eighteen(round_.holes))

        return sorted(
            (
                CoursePerformance(
                    golf_course_id=course_id,
                    golf_course_name=nombre,
                    rounds=len(vueltas),
                    average_to_par=round(sum(vueltas) / len(vueltas), 1),
                )
                for course_id, (nombre, vueltas) in por_campo.items()
            ),
            key=lambda item: item.average_to_par,
        )

    @staticmethod
    def _round_to_par_over_eighteen(holes: list[HoleOutcome]) -> float:
        """
        Lo que la vuelta hizo sobre el par, llevado a la escala de 18.

        Es la misma corrección que aplica `scoring_avg`, y por el mismo motivo:
        sin ella, jugar medias vueltas parecería mejorar el juego.
        """
        to_par = sum(hole.net_to_par for hole in holes)
        return to_par * (_ROUND_HOLES / len(holes))

    @staticmethod
    def _average(values: list[int]) -> float:
        return round(sum(values) / len(values), 2)
