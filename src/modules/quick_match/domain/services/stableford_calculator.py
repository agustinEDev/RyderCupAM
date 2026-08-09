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

HOLES_PER_ROUND = 18


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

    def compute_participant_totals(
        self,
        handicap: float | None,
        holes: list[HoleSetup],
        scores_by_hole: dict[int, int],
        tee_rating: TeeRating | None = None,
        allowance_percentage: int = 100,
    ) -> ParticipantTotals:
        """
        Agrega puntos y golpes de un participante sobre los hoyos anotados.

        Los hoyos sin score no cuentan: una partida a medias puntúa por lo
        jugado, no por lo que falta.
        """
        strokes_basis = self.resolve_strokes_basis(handicap, tee_rating, allowance_percentage)

        stableford_points = 0
        total_strokes = 0
        net_strokes = 0
        par_played = 0
        holes_played = 0

        for hole in holes:
            score = scores_by_hole.get(hole.hole_number)
            if score is None:
                continue

            strokes_received = self.allocate_strokes(strokes_basis, hole.stroke_index)
            stableford_points += self.hole_points(score, hole.par, strokes_received)
            total_strokes += score
            net_strokes += score - strokes_received
            par_played += hole.par
            holes_played += 1

        return ParticipantTotals(
            stableford_points=stableford_points,
            total_strokes=total_strokes,
            net_strokes=net_strokes,
            par_played=par_played,
            holes_played=holes_played,
        )

    @staticmethod
    def format_to_par(to_par: int) -> str:
        """Notación de golf: "PAR" si iguala, y con signo si no ("-3", "+4")."""
        if to_par == 0:
            return "PAR"
        return f"+{to_par}" if to_par > 0 else str(to_par)
