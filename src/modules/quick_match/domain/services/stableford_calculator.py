"""
Domain Service: StablefordCalculator.

Calcula puntos Stableford y totales de golpes de los participantes de una
partida rápida. Puro, sin IO.

Portado del `StablefordCalculator` del frontend (BE #128), que hasta ahora era
el único sitio donde vivían estas reglas. Mientras las dos implementaciones
coexistan, `tests/unit/modules/quick_match/domain/services/
test_stableford_calculator.py` fija la paridad con los valores que el frontend
produce hoy.

Puntos por hoyo: max(0, 2 - (neto - par)).
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from src.modules.competition.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)

# El catálogo solo admite campos de 18 hoyos: `GolfCourse` lo valida como
# invariante y rechaza cualquier otro número. Por eso el reparto de golpes es
# una constante y no se deriva del campo. El día que se admitan campos de nueve
# hay que derivarlo de los hoyos recibidos, aquí y en la inversión del 19.
HOLES_PER_ROUND = 18

# Doble bogey neto: el tope por hoyo que el WHS aplica a lo que puntúa para
# hándicap (Regla 3.1)
NET_DOUBLE_BOGEY_OVER_PAR = 2


@dataclass(frozen=True)
class HoleSetup:
    """Un hoyo del campo: su par y su dificultad relativa."""

    hole_number: int
    par: int
    stroke_index: int


@dataclass(frozen=True)
class ParticipantTotals:
    """Totales de un participante sobre los hoyos que ya tienen score."""

    stableford_points: int
    total_strokes: int
    net_strokes: int
    par_played: int
    holes_played: int
    adjusted_gross_strokes: int

    @property
    def to_par(self) -> int:
        """Golpes netos respecto al par de lo jugado."""
        return self.net_strokes - self.par_played


class StablefordCalculator:
    """Puntuación Stableford y golpes netos de una partida rápida."""

    def __init__(self, playing_handicap_calculator: PlayingHandicapCalculator | None = None):
        self._playing_handicap_calculator = (
            playing_handicap_calculator or PlayingHandicapCalculator()
        )

    def resolve_strokes_basis(
        self,
        handicap: float | None,
        tee_rating: TeeRating | None,
        allowance_percentage: int,
    ) -> Decimal | None:
        """
        Hándicap con el que se reparten los golpes.

        Si el participante eligió un tee del campo, su Playing Handicap; si no,
        su hándicap tal cual contra el stroke index. Devuelve None cuando no hay
        hándicap conocido: ese participante no recibe golpes.
        """
        if handicap is None:
            return None
        if tee_rating is None:
            return Decimal(str(handicap))

        # Sin acotar: un jugador plus cede golpes (Regla WHS 8.2)
        playing_handicap = self._playing_handicap_calculator.calculate_unbounded(
            Decimal(str(handicap)), tee_rating, allowance_percentage
        )
        return Decimal(playing_handicap)

    @staticmethod
    def allocate_strokes(handicap: Decimal | None, stroke_index: int) -> int:
        """
        Golpes que recibe (o cede, si es plus) un participante en un hoyo.

        stroke_index va de 1 (el hoyo más difícil) a 18 (el más fácil).
        """
        if handicap is None:
            return 0

        # floor(x + 0.5), que es lo que hace `Math.round` en el frontend: el
        # medio va siempre hacia arriba, tambien en negativos (-2.5 -> -2).
        # ROUND_HALF_UP de Decimal se aleja del cero y daria -3.
        rounded = int((handicap + Decimal("0.5")).to_integral_value(rounding=ROUND_FLOOR))
        if rounded == 0:
            return 0

        if rounded > 0:
            base = rounded // HOLES_PER_ROUND
            extra = 1 if (rounded % HOLES_PER_ROUND) >= stroke_index else 0
            return base + extra

        # Jugador plus: la Regla WHS 8.2 quita golpes empezando por el hoyo más
        # fácil (stroke index más alto) y hacia atrás
        magnitude = abs(rounded)
        base = -(magnitude // HOLES_PER_ROUND)
        extra = -1 if (magnitude % HOLES_PER_ROUND) >= (19 - stroke_index) else 0
        return base + extra

    @staticmethod
    def hole_points(gross_score: int | None, par: int, strokes_received: int) -> int:
        """Puntos Stableford de un hoyo."""
        if gross_score is None:
            return 0
        net_score = gross_score - strokes_received
        return max(0, 2 - (net_score - par))

    @staticmethod
    def adjusted_gross(gross_score: int, par: int, strokes_received: int) -> int:
        """
        Golpes del hoyo topados en el net double bogey (Regla WHS 3.1).

        Máximo computable: doble bogey neto, o sea `par + 2 + golpes recibidos`.
        Sin ese tope, un hoyo desastroso mueve la media de una temporada entera,
        que es justo lo que la regla existe para evitar.

        No afecta a los puntos Stableford: un hoyo en net double bogey ya vale
        cero puntos, y a partir de ahí sigue valiendo cero.
        """
        return min(gross_score, par + NET_DOUBLE_BOGEY_OVER_PAR + strokes_received)

    def compute_participant_totals(
        self,
        handicap: float | None,
        holes: list[HoleSetup],
        scores_by_hole: dict[int, int],
        tee_rating: TeeRating | None = None,
        allowance_percentage: int = 100,
        cap_at_net_double_bogey: bool = False,
    ) -> ParticipantTotals:
        """
        Agrega puntos y golpes de un participante sobre los hoyos anotados.

        Los hoyos sin score no cuentan: una partida a medias puntúa por lo
        jugado, no por lo que falta.

        `cap_at_net_double_bogey` topa cada hoyo en el máximo que el WHS deja
        computar para hándicap. Va apagado por defecto porque el detalle de la
        partida enseña los golpes que se dieron, no los que puntúan; lo encienden
        las estadísticas agregadas, donde un hoyo suelto no debe pesar más que
        una temporada.

        `adjusted_gross_strokes` sale siempre topado, mire o no `net_strokes` al
        tope: es el Adjusted Gross Score del WHS, que por definición lo lleva, y
        de él sale el Score Differential de la vuelta (BE #167).
        """
        strokes_basis = self.resolve_strokes_basis(handicap, tee_rating, allowance_percentage)

        stableford_points = 0
        total_strokes = 0
        net_strokes = 0
        par_played = 0
        holes_played = 0
        adjusted_gross_strokes = 0

        for hole in holes:
            score = scores_by_hole.get(hole.hole_number)
            if score is None:
                continue

            strokes_received = self.allocate_strokes(strokes_basis, hole.stroke_index)
            stableford_points += self.hole_points(score, hole.par, strokes_received)
            total_strokes += score
            adjusted = self.adjusted_gross(score, hole.par, strokes_received)
            adjusted_gross_strokes += adjusted
            computable = adjusted if cap_at_net_double_bogey else score
            net_strokes += computable - strokes_received
            par_played += hole.par
            holes_played += 1

        return ParticipantTotals(
            stableford_points=stableford_points,
            total_strokes=total_strokes,
            net_strokes=net_strokes,
            par_played=par_played,
            holes_played=holes_played,
            adjusted_gross_strokes=adjusted_gross_strokes,
        )

    @staticmethod
    def format_to_par(to_par: int) -> str:
        """Notación de golf: "PAR" si iguala, y con signo si no ("-3", "+4")."""
        if to_par == 0:
            return "PAR"
        return f"+{to_par}" if to_par > 0 else str(to_par)
