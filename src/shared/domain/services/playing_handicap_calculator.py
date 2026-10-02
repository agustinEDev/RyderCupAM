"""
PlayingHandicapCalculator Domain Service.

Calcula el Playing Handicap (Handicap de Juego) según el World Handicap System (WHS).

Fórmula WHS:
Playing Handicap = (Handicap Index x (Slope Rating / 113) + (Course Rating - Par)) x Allowance%

El resultado se redondea al entero más cercano (0.5 redondea hacia arriba).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Porcentajes que se pueden elegir a mano (50-100, de 5 en 5). Estaban dos veces,
# en `Round` y en `QuickMatch` (RyderCupAM#165); los por defecto los da MatchFormat
ALLOWED_ALLOWANCE_PERCENTAGES = frozenset(range(50, 101, 5))


def round_half_up(value: Decimal) -> int:
    """
    El redondeo de todo el cálculo de hándicap: los .5 se alejan del cero.

    20.5 -> 21, 21.5 -> 22 y -2.5 -> -3, que es lo que hace
    `roundHalfAwayFromZero` en el frontend. `round()` de Python y
    `Decimal.to_integral_value()` redondean al par en los .5 (20.5 -> 20), y los
    hándicaps acabados en .5 son de lo más común. Estaba copiado cinco veces
    (RyderCupAM#165).
    """
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# Slope Rating neutral (valor estándar del sistema WHS)
NEUTRAL_SLOPE = 113

# Rangos absolutos, unión de los de todos los tipos de campo: aquí solo se
# descarta lo que no puede ser válido en ninguno. Son los mismos que valida la
# entidad `Tee` (golf_course), y el rango estricto que corresponde a cada tipo
# lo comprueba `GolfCourse._validate_tee_ratings`, que es quien conoce el
# `course_type`. Este dominio no puede conocerlo sin depender de `golf_course`.
#
# Antes eran los de un campo de 18 hoyos (CR 55-85, SR 55-155, par 66-76) y no
# los de todos los tipos, así que rechazaban lo que la propia entidad `Tee`
# admite: en el catálogo federado hay 468 salidas en 227 campos con CR por
# debajo de 55, y 642 con par por debajo de 66 —los pitch & putt y los
# ejecutivos, que el sistema no valora en la misma escala—. Un campo entero se
# quedaba sin poder alojar competición, y en partida rápida sus jugadores
# jugaban con el Handicap Index a pelo: un 18 recibía 18 golpes donde le tocan
# 11. Ver RyderCupAm#206 y RyderCupAm#219.
MIN_COURSE_RATING = 45
MAX_COURSE_RATING = 90
MIN_SLOPE_RATING = 40
MAX_SLOPE_RATING = 160
# El catálogo federado va de 54 (pitch & putt) a 74; el margen deja sitio a un
# recorrido más corto sin llegar a admitir un par imposible.
MIN_PAR = 50
MAX_PAR = 80


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
            raise ValueError(f"par must be between {MIN_PAR} and {MAX_PAR}, got {self.par}")


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
        max_playing_handicap: int | None = None,
    ) -> int:
        """
        Calcula el Playing Handicap (Handicap de Juego).

        Fórmula WHS:
        Playing Handicap = (HI x (SR / 113) + (CR - Par)) x Allowance%

        Args:
            handicap_index: Handicap Index del jugador (ej: 12.4)
            tee_rating: Ratings del tee (CR, SR, Par)
            allowance_percentage: Porcentaje de allowance (50-100)
            max_playing_handicap: Límite superior opcional (cap WHS de la competición)

        Returns:
            Playing Handicap redondeado al entero más cercano (>=0), acotado a
            max_playing_handicap si se proporciona
        """
        playing_handicap = self.calculate_unbounded(
            handicap_index, tee_rating, allowance_percentage
        )

        # Playing Handicap no puede ser negativo
        result = max(0, playing_handicap)
        if max_playing_handicap is not None:
            result = min(result, max_playing_handicap)
        return result

    def calculate_unbounded(
        self,
        handicap_index: Decimal,
        tee_rating: TeeRating,
        allowance_percentage: int,
    ) -> int:
        """
        Playing Handicap sin acotar a cero, para jugadores de hándicap plus.

        `calculate()` acota el resultado a >= 0, de modo que un jugador plus no
        llega a ceder golpes. Eso vale para el flujo de competición, que es
        donde se usa, pero no para la clasificación Stableford de una partida
        rápida: ahí un plus sí cede golpes (Regla WHS 8.2), y es lo que el
        frontend viene calculando y mostrando.

        Se expone como método propio en lugar de cambiar `calculate()` para no
        alterar el reparto de golpes de las competiciones ya creadas.
        """
        # CH = HI x (SR / 113) + (CR - Par)
        slope_factor = Decimal(tee_rating.slope_rating) / Decimal(NEUTRAL_SLOPE)
        differential = tee_rating.course_rating - Decimal(tee_rating.par)
        course_handicap = (handicap_index * slope_factor) + differential

        allowance_factor = Decimal(allowance_percentage) / Decimal(100)
        playing_handicap_raw = course_handicap * allowance_factor

        return round_half_up(playing_handicap_raw)

    def calculate_course_handicap(
        self,
        handicap_index: Decimal,
        tee_rating: TeeRating,
    ) -> int:
        """
        Calcula el Course Handicap (sin allowance), redondeado al entero más cercano.

        CH = HI x (SR / 113) + (CR - Par)

        Args:
            handicap_index: Handicap Index del jugador
            tee_rating: Ratings del tee

        Returns:
            Course Handicap redondeado (>= 0)
        """
        raw = self._calculate_course_handicap(handicap_index, tee_rating)
        return max(0, round_half_up(raw))

    @staticmethod
    def calculate_fourball_differential(
        player_course_handicaps: list[tuple[str, int]],
        allowance_percentage: int,
        max_playing_handicap: int | None = None,
    ) -> dict[str, int]:
        """
        Método diferencial WHS para Fourball (Match Play).

        En lugar de aplicar el porcentaje de allowance a cada handicap individual,
        se aplica a la DIFERENCIA respecto al jugador con menor course handicap.
        El jugador de menor CH juega off scratch (0 strokes).

        Fórmula:
        1. Encontrar el menor course handicap entre los 4 jugadores
        2. Para cada jugador: diferencia = CH - menor_CH
        3. Playing Handicap = diferencia x allowance_percentage / 100
        4. Si se indica max_playing_handicap, se acota a ese límite

        Args:
            player_course_handicaps: Lista de (user_id, course_handicap) para los 4 jugadores
            allowance_percentage: Porcentaje de allowance de la ronda (50-100)
            max_playing_handicap: Límite superior opcional (cap WHS de la competición)

        Returns:
            dict de user_id → playing_handicap diferencial (acotado si se indica el cap)
        """
        if not player_course_handicaps:
            return {}

        lowest_ch = min(ch for _, ch in player_course_handicaps)
        allowance = Decimal(str(allowance_percentage)) / Decimal("100")

        result: dict[str, int] = {}
        for user_id, ch in player_course_handicaps:
            diff = ch - lowest_ch
            ph = round_half_up(Decimal(str(diff)) * allowance)
            if max_playing_handicap is not None:
                ph = min(ph, max_playing_handicap)
            result[user_id] = ph
        return result

    @staticmethod
    def calculate_singles_differential(
        ph_a: int,
        ph_b: int,
        holes_by_stroke_index: list[int],
    ) -> tuple[list[int], list[int]]:
        """
        Método diferencial WHS para Singles (Match Play).

        Solo el jugador con mayor Playing Handicap recibe golpes, en los hoyos
        más difíciles (menor Stroke Index). El jugador de menor PH juega off
        scratch (0 golpes recibidos). Si ambos PH son iguales, ninguno recibe.

        Args:
            ph_a: Playing Handicap del jugador A (ya con allowance aplicado)
            ph_b: Playing Handicap del jugador B (ya con allowance aplicado)
            holes_by_stroke_index: Números de hoyo ordenados por stroke index

        Returns:
            (strokes_a, strokes_b) — hoyos donde cada jugador recibe golpe.
            Exactamente una de las dos listas tendrá elementos (o ninguna, si
            ph_a == ph_b).
        """
        diff = ph_a - ph_b
        if diff > 0:
            return PlayingHandicapCalculator.compute_strokes_received(
                diff, holes_by_stroke_index
            ), []
        if diff < 0:
            return [], PlayingHandicapCalculator.compute_strokes_received(
                -diff, holes_by_stroke_index
            )
        return [], []

    @staticmethod
    def calculate_foursomes_differential(
        team_a_course_handicaps: list[int],
        team_b_course_handicaps: list[int],
        allowance_percentage: int,
        max_playing_handicap: int | None = None,
    ) -> tuple[int, int]:
        """
        Método diferencial WHS para Foursomes (Golpe Alterno).

        En FOURSOMES, los strokes se calculan a nivel de EQUIPO (no individual):
        1. Promediar los Course Handicaps de cada equipo
        2. Calcular diferencia entre promedios
        3. Aplicar allowance_percentage a la diferencia
        4. El equipo con mayor promedio CH recibe los strokes; el otro recibe 0
        5. Si se indica max_playing_handicap, se acota a ese límite

        Ambos jugadores del equipo reciben los mismos strokes porque
        comparten una bola (golpe alterno).

        Args:
            team_a_course_handicaps: CHs de los jugadores del equipo A
            team_b_course_handicaps: CHs de los jugadores del equipo B
            allowance_percentage: Porcentaje de allowance de la ronda (50-100)
            max_playing_handicap: Límite superior opcional (cap WHS de la competición)

        Returns:
            (team_a_ph, team_b_ph) — Playing Handicap por equipo (acotado si se indica
            el cap). Solo un equipo recibe strokes (el de mayor CH promedio).
        """
        if not team_a_course_handicaps or not team_b_course_handicaps:
            return 0, 0

        team_a_avg = Decimal(str(sum(team_a_course_handicaps))) / Decimal(
            str(len(team_a_course_handicaps))
        )
        team_b_avg = Decimal(str(sum(team_b_course_handicaps))) / Decimal(
            str(len(team_b_course_handicaps))
        )

        difference = abs(team_a_avg - team_b_avg)
        allowance = Decimal(str(allowance_percentage)) / Decimal("100")
        strokes = round_half_up(difference * allowance)
        if max_playing_handicap is not None:
            strokes = min(strokes, max_playing_handicap)

        if team_a_avg > team_b_avg:
            return strokes, 0
        if team_b_avg > team_a_avg:
            return 0, strokes
        return 0, 0

    @staticmethod
    def compute_strokes_received(
        playing_handicap: int,
        holes_by_stroke_index: list[int],
    ) -> list[int]:
        """
        Calcula los hoyos donde el jugador recibe golpe, basado en stroke_index.

        Distribuye strokes siguiendo el orden de stroke index de los hoyos.
        Si playing_handicap > 18, se vuelve a recorrer la lista (wrap-around),
        generando entradas duplicadas para hoyos que reciben más de un golpe.

        Ejemplo: PH=29 con 18 hoyos → los primeros 11 hoyos por SI aparecen
        2 veces (2 strokes), los últimos 7 aparecen 1 vez (1 stroke).

        Use strokes_on_hole(hole_number, strokes_received) para obtener
        el conteo de strokes en un hoyo específico.

        Args:
            playing_handicap: Playing Handicap calculado del jugador
            holes_by_stroke_index: Números de hoyo ordenados por stroke index

        Returns:
            Lista de números de hoyo donde el jugador recibe golpe
            (puede contener duplicados si PH > 18)
        """
        if not holes_by_stroke_index or playing_handicap <= 0:
            return []

        result: list[int] = []
        remaining = playing_handicap
        while remaining > 0:
            take = min(remaining, len(holes_by_stroke_index))
            result.extend(holes_by_stroke_index[:take])
            remaining -= take

        return result

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
