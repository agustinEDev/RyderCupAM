"""
PlayingHandicapCalculator Domain Service.

Calcula el Playing Handicap (Handicap de Juego) según el World Handicap System (WHS).

Fórmula WHS:
Playing Handicap = (Handicap Index x (Slope Rating / 113) + (Course Rating - Par)) x Allowance%

El resultado se redondea al entero más cercano (0.5 redondea hacia arriba).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from src.modules.competition.domain.entities.round import (
    FOURBALL_ALLOWANCE,
    FOURSOMES_ALLOWANCE,
)
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode

# Slope Rating neutral (valor estándar del sistema WHS)
NEUTRAL_SLOPE = 113

# Límites válidos para ratings de tees según WHS
MIN_COURSE_RATING = 55
MAX_COURSE_RATING = 85
MIN_SLOPE_RATING = 55
MAX_SLOPE_RATING = 155
MIN_PAR = 66
MAX_PAR = 76


@dataclass(frozen=True)
class TeeRating:
    """
    Ratings de un tee según WHS.

    Attributes:
        course_rating: CR (Course Rating) - dificultad para un scratch player
        slope_rating: SR (Slope Rating) - dificultad relativa para bogey vs scratch
        par: Par total del campo desde ese tee
    """

    course_rating: Decimal
    slope_rating: int
    par: int

    def __post_init__(self) -> None:
        """Valida los ratings."""
        if not MIN_COURSE_RATING <= self.course_rating <= MAX_COURSE_RATING:
            raise ValueError(
                f"course_rating must be between {MIN_COURSE_RATING}.0 and {MAX_COURSE_RATING}.0, "
                f"got {self.course_rating}"
            )
        if not MIN_SLOPE_RATING <= self.slope_rating <= MAX_SLOPE_RATING:
            raise ValueError(
                f"slope_rating must be between {MIN_SLOPE_RATING} and {MAX_SLOPE_RATING}, "
                f"got {self.slope_rating}"
            )
        if not MIN_PAR <= self.par <= MAX_PAR:
            raise ValueError(
                f"par must be between {MIN_PAR} and {MAX_PAR}, got {self.par}"
            )


class PlayingHandicapCalculator:
    """
    Servicio de dominio para calcular Playing Handicaps según WHS.

    Este servicio encapsula la lógica del World Handicap System para
    calcular el handicap de juego efectivo de un jugador, considerando:
    - Su Handicap Index oficial
    - Los ratings del tee desde el que juega (CR, SR, Par)
    - El porcentaje de allowance según el formato de partido

    Uso:
        calculator = PlayingHandicapCalculator()
        playing_handicap = calculator.calculate(
            handicap_index=Decimal("12.4"),
            tee_rating=TeeRating(course_rating=Decimal("71.2"), slope_rating=128, par=72),
            allowance_percentage=95,
        )
    """

    def calculate(
        self,
        handicap_index: Decimal,
        tee_rating: TeeRating,
        allowance_percentage: int,
    ) -> int:
        """
        Calcula el Playing Handicap (Handicap de Juego).

        Fórmula WHS:
        Playing Handicap = (HI x (SR / 113) + (CR - Par)) x Allowance%

        Args:
            handicap_index: Handicap Index del jugador (ej: 12.4)
            tee_rating: Ratings del tee (CR, SR, Par)
            allowance_percentage: Porcentaje de allowance (50-100)

        Returns:
            Playing Handicap redondeado al entero más cercano (>=0)
        """
        # Paso 1: Calcular Course Handicap
        # CH = HI x (SR / 113) + (CR - Par)
        slope_factor = Decimal(tee_rating.slope_rating) / Decimal(NEUTRAL_SLOPE)
        differential = tee_rating.course_rating - Decimal(tee_rating.par)
        course_handicap = (handicap_index * slope_factor) + differential

        # Paso 2: Aplicar allowance
        allowance_factor = Decimal(allowance_percentage) / Decimal(100)
        playing_handicap_raw = course_handicap * allowance_factor

        # Paso 3: Redondear al entero más cercano (0.5 hacia arriba)
        playing_handicap = int(
            playing_handicap_raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

        # Playing Handicap no puede ser negativo
        return max(0, playing_handicap)

    def calculate_for_singles(
        self,
        player_hi: Decimal,
        player_tee: TeeRating,
        opponent_hi: Decimal,
        opponent_tee: TeeRating,
        handicap_mode: HandicapMode,
        custom_allowance: int | None = None,
    ) -> tuple[int, int]:
        """
        Calcula los Playing Handicaps para un partido SINGLES.

        En SINGLES, los strokes se dan basados en la DIFERENCIA
        entre los playing handicaps de ambos jugadores.

        Args:
            player_hi: Handicap Index del jugador
            player_tee: TeeRating del jugador
            opponent_hi: Handicap Index del oponente
            opponent_tee: TeeRating del oponente
            handicap_mode: STROKE_PLAY (95%) o MATCH_PLAY (100%)
            custom_allowance: Allowance personalizado (opcional)

        Returns:
            Tuple (player_ph, opponent_ph) con Playing Handicaps
        """
        allowance = custom_allowance or handicap_mode.default_allowance()

        player_ph = self.calculate(player_hi, player_tee, allowance)
        opponent_ph = self.calculate(opponent_hi, opponent_tee, allowance)

        return player_ph, opponent_ph

    def calculate_for_fourball(
        self,
        player1_hi: Decimal,
        player1_tee: TeeRating,
        player2_hi: Decimal,
        player2_tee: TeeRating,
        custom_allowance: int | None = None,
    ) -> tuple[int, int]:
        """
        Calcula los Playing Handicaps para un equipo en FOURBALL.

        En FOURBALL (mejor bola), cada jugador usa su propio
        Playing Handicap. El allowance por defecto es 90%.

        Args:
            player1_hi: Handicap Index del jugador 1
            player1_tee: TeeRating del jugador 1
            player2_hi: Handicap Index del jugador 2
            player2_tee: TeeRating del jugador 2
            custom_allowance: Allowance personalizado (opcional)

        Returns:
            Tuple (player1_ph, player2_ph) con Playing Handicaps
        """
        allowance = custom_allowance or FOURBALL_ALLOWANCE

        player1_ph = self.calculate(player1_hi, player1_tee, allowance)
        player2_ph = self.calculate(player2_hi, player2_tee, allowance)

        return player1_ph, player2_ph

    def calculate_for_foursomes(
        self,
        team1_hi_avg: Decimal,
        team1_tee: TeeRating,
        team2_hi_avg: Decimal,
        team2_tee: TeeRating,
        custom_allowance: int | None = None,
    ) -> tuple[int, int]:
        """
        Calcula los Playing Handicaps para equipos en FOURSOMES.

        En FOURSOMES (golpe alterno), se usa el promedio de los
        Handicap Index de cada equipo. El allowance (default 50%)
        se aplica a la DIFERENCIA entre los course handicaps de
        los equipos, no a cada handicap individual.

        Fórmula WHS para FOURSOMES:
        1. Calcular Course Handicap combinado de cada equipo
        2. Calcular diferencia: |CH_team1 - CH_team2|
        3. Aplicar 50% a la diferencia
        4. El equipo con mayor CH recibe los strokes

        Args:
            team1_hi_avg: Promedio de Handicap Index del equipo 1
            team1_tee: TeeRating del equipo 1 (ambos deben jugar mismo tee)
            team2_hi_avg: Promedio de Handicap Index del equipo 2
            team2_tee: TeeRating del equipo 2
            custom_allowance: Allowance personalizado (opcional, default 50%)

        Returns:
            Tuple (team1_strokes, team2_strokes) donde el equipo con
            mayor Course Handicap recibe strokes y el otro recibe 0.

        Example:
            Team A: avg HI = 15.0, CH = 17
            Team B: avg HI = 10.0, CH = 11
            Diferencia = 6, 50% = 3 strokes
            Resultado: (3, 0) - Team A recibe 3 strokes
        """
        allowance = custom_allowance or FOURSOMES_ALLOWANCE

        # Calcular Course Handicaps (sin allowance, para calcular diferencia)
        team1_ch = self._calculate_course_handicap(team1_hi_avg, team1_tee)
        team2_ch = self._calculate_course_handicap(team2_hi_avg, team2_tee)

        # Calcular diferencia y aplicar allowance
        difference = abs(team1_ch - team2_ch)
        allowance_factor = Decimal(allowance) / Decimal(100)
        strokes_raw = difference * allowance_factor

        # Redondear strokes
        strokes = int(strokes_raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # Asignar strokes al equipo con mayor CH
        if team1_ch > team2_ch:
            return strokes, 0
        if team2_ch > team1_ch:
            return 0, strokes
        return 0, 0  # Mismo CH, nadie recibe strokes

    def _calculate_course_handicap(
        self,
        handicap_index: Decimal,
        tee_rating: TeeRating,
    ) -> Decimal:
        """
        Calcula el Course Handicap (sin allowance).

        CH = HI x (SR / 113) + (CR - Par)
        """
        slope_factor = Decimal(tee_rating.slope_rating) / Decimal(NEUTRAL_SLOPE)
        differential = tee_rating.course_rating - Decimal(tee_rating.par)
        return (handicap_index * slope_factor) + differential
