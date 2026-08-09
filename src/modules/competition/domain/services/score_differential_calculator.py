"""
Domain Service: ScoreDifferentialCalculator.

Score Differential del WHS: el hándicap al que un jugador jugó una vuelta
concreta, y el índice estimado que sale de sus últimas vueltas. Puro, sin IO.

Vive junto a `PlayingHandicapCalculator` porque son la misma familia de reglas
WHS y comparten `TeeRating`, aunque ninguno de los dos sea exclusivo del módulo
de competición.

**Este índice no es el oficial de la federación.** Falta el PCC (Playing
Conditions Calculation), que ajusta los diferenciales por cómo estaba el campo
ese día y que solo puede calcular quien tiene todas las tarjetas de la jornada.
Aquí se asume PCC = 0.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from src.modules.competition.domain.services.playing_handicap_calculator import (
    NEUTRAL_SLOPE,
    TeeRating,
)

# Ventana de vueltas del WHS: el índice mira las 20 últimas, no la carrera
# entera. Un jugador que mejora no arrastra sus vueltas de hace tres años.
SCORING_RECORD_SIZE = 20

# Sin al menos estas vueltas no se publica índice. El WHS pide 54 hoyos, que
# son tres vueltas: con dos, el número es ruido con aspecto de dato.
MIN_ROUNDS_FOR_INDEX = 3

# Cuántas vueltas se promedian y qué ajuste se les aplica, según cuántas hay
# disponibles (Regla WHS 5.2). Con pocas vueltas se coge solo la mejor y se le
# resta un margen: la muestra es tan pequeña que sin ese ajuste el índice
# saldría optimista. Cada entrada es (mínimo de vueltas, cuántas se promedian,
# ajuste), ordenada de más a menos vueltas.
_INDEX_TABLE: tuple[tuple[int, int, Decimal], ...] = (
    (20, 8, Decimal("0")),
    (19, 7, Decimal("0")),
    (17, 6, Decimal("0")),
    (15, 5, Decimal("0")),
    (12, 4, Decimal("0")),
    (9, 3, Decimal("0")),
    (7, 2, Decimal("0")),
    (6, 2, Decimal("-1.0")),
    (5, 1, Decimal("0")),
    (4, 1, Decimal("-1.0")),
    (3, 1, Decimal("-2.0")),
)

# Cuántas vueltas entran en cada mitad de la comparación de tendencia. Cinco es
# suficiente para que una vuelta mala no dicte la tendencia, y bastante poco
# para que la tendencia hable del presente.
TREND_WINDOW = 5


@dataclass(frozen=True)
class PlayedRound:
    """
    Una vuelta ya reducida a lo que el WHS necesita de ella.

    `adjusted_gross_score` son los golpes de la vuelta con cada hoyo topado en
    su net double bogey; el tope se aplica antes, al leer la tarjeta, porque
    depende de los golpes que el jugador recibía en cada hoyo.
    """

    adjusted_gross_score: int
    tee_rating: TeeRating


class ScoreDifferentialCalculator:
    """Diferenciales de vuelta e índice estimado, según el WHS."""

    @staticmethod
    def differential(played_round: PlayedRound) -> Decimal:
        """
        A qué hándicap se jugó esa vuelta.

        `(113 / Slope) x (Golpes ajustados - Course Rating)`: la resta dice
        cuánto peor (o mejor) se jugó que un scratch desde ese tee, y el factor
        de slope traduce ese margen a la escala neutra del sistema, para que una
        vuelta en un campo durísimo y otra en uno fácil sean comparables.
        """
        rating = played_round.tee_rating
        raw = (Decimal(NEUTRAL_SLOPE) / Decimal(rating.slope_rating)) * (
            Decimal(played_round.adjusted_gross_score) - rating.course_rating
        )
        return raw.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @classmethod
    def differentials(cls, played_rounds: list[PlayedRound]) -> list[Decimal]:
        """Diferenciales en el mismo orden en que llegan las vueltas."""
        return [cls.differential(played_round) for played_round in played_rounds]

    @staticmethod
    def estimated_index(differentials: list[Decimal]) -> Decimal | None:
        """
        Índice estimado a partir de los diferenciales, del más reciente al más
        antiguo.

        Se queda con los 20 más recientes y promedia los mejores según la tabla
        del WHS. Devuelve None por debajo de tres vueltas: no es un índice de
        cero, es que todavía no hay con qué calcularlo.
        """
        window = differentials[:SCORING_RECORD_SIZE]
        if len(window) < MIN_ROUNDS_FOR_INDEX:
            return None

        count, adjustment = next(
            (used, adjust) for minimum, used, adjust in _INDEX_TABLE if len(window) >= minimum
        )
        best = sorted(window)[:count]
        average = sum(best, Decimal("0")) / Decimal(count)
        return (average + adjustment).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @staticmethod
    def playing_average(differentials: list[Decimal]) -> Decimal | None:
        """
        Media de los diferenciales recientes, buenos y malos.

        El índice mira solo las mejores vueltas, que es su regla y su virtud:
        dice de lo que un jugador es capaz. Esta media dice a qué juega de
        media, incluidos los días malos, y suele ser varios golpes peor.
        """
        window = differentials[:SCORING_RECORD_SIZE]
        if not window:
            return None
        average = sum(window, Decimal("0")) / Decimal(len(window))
        return average.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @staticmethod
    def best_differential(differentials: list[Decimal]) -> Decimal | None:
        """La mejor vuelta del registro: el diferencial más bajo."""
        window = differentials[:SCORING_RECORD_SIZE]
        return min(window) if window else None

    @staticmethod
    def trend(differentials: list[Decimal]) -> Decimal | None:
        """
        Cuánto ha cambiado el juego, comparando las vueltas recientes con las
        anteriores.

        **Negativo es mejorar**: los diferenciales bajan cuando se juega mejor,
        igual que baja un hándicap. Se devuelve la resta cruda, sin invertir el
        signo, para que el número no contradiga al hándicap que la interfaz
        enseña a su lado.

        None mientras no haya dos ventanas completas que comparar: con menos
        vueltas la "tendencia" sería la diferencia entre dos vueltas sueltas.
        """
        if len(differentials) < TREND_WINDOW * 2:
            return None

        recent = differentials[:TREND_WINDOW]
        previous = differentials[TREND_WINDOW : TREND_WINDOW * 2]
        change = (sum(recent, Decimal("0")) - sum(previous, Decimal("0"))) / Decimal(TREND_WINDOW)
        return change.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
