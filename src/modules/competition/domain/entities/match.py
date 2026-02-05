"""
Match Entity - Partido de una sesión.

Representa un partido individual dentro de una sesión de competición.
"""

from datetime import datetime

from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId


class Match:
    """
    Entidad que representa un partido de golf.

    Un partido enfrenta a jugadores del Equipo A contra jugadores del Equipo B.
    Según el formato:
    - SINGLES: 1 vs 1
    - FOURBALL: 2 vs 2 (mejor bola)
    - FOURSOMES: 2 vs 2 (golpes alternados)

    Cada jugador tiene su playing handicap calculado según su tee elegido
    en el Enrollment y los ratings del campo de la sesión.

    Características DDD:
    - Es una Entity (tiene identidad: MatchId)
    - Vive dentro del contexto de Round
    - Contiene MatchPlayer como Value Objects embebidos
    """

    def __init__(
        self,
        id: MatchId,
        round_id: RoundId,
        match_number: int,
        team_a_players: tuple[MatchPlayer, ...],
        team_b_players: tuple[MatchPlayer, ...],
        status: MatchStatus,
        handicap_strokes_given: int,
        strokes_given_to_team: str,
        result: dict | None,
        created_at: datetime,
        updated_at: datetime,
    ):
        """Constructor privado (usar factory methods)."""
        self._id = id
        self._round_id = round_id
        self._match_number = match_number
        self._team_a_players = team_a_players
        self._team_b_players = team_b_players
        self._status = status
        self._handicap_strokes_given = handicap_strokes_given
        self._strokes_given_to_team = strokes_given_to_team
        self._result = result
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def create(
        cls,
        round_id: RoundId,
        match_number: int,
        team_a_players: list[MatchPlayer],
        team_b_players: list[MatchPlayer],
    ) -> "Match":
        """
        Factory method para crear un nuevo partido.

        Calcula automáticamente los golpes de ventaja basándose en
        los playing handicaps de los equipos.

        Args:
            round_id: ID de la sesión
            match_number: Número de partido en la sesión (1, 2, 3...)
            team_a_players: Jugadores del Equipo A
            team_b_players: Jugadores del Equipo B

        Returns:
            Nueva instancia de Match con status SCHEDULED

        Raises:
            ValueError: Si los equipos no tienen el mismo número de jugadores
        """
        if len(team_a_players) != len(team_b_players):
            raise ValueError(
                f"Teams must have equal players. "
                f"Team A: {len(team_a_players)}, Team B: {len(team_b_players)}"
            )

        if not team_a_players:
            raise ValueError("Teams cannot be empty")

        if match_number < 1:
            raise ValueError(f"match_number must be >= 1, got {match_number}")

        # Calcular handicap combinado de cada equipo
        team_a_handicap = sum(p.playing_handicap for p in team_a_players)
        team_b_handicap = sum(p.playing_handicap for p in team_b_players)

        # Determinar golpes de ventaja
        handicap_diff = abs(team_a_handicap - team_b_handicap)
        if team_a_handicap > team_b_handicap:
            strokes_given_to_team = "A"
        elif team_b_handicap > team_a_handicap:
            strokes_given_to_team = "B"
        else:
            strokes_given_to_team = ""

        now = datetime.now()
        return cls(
            id=MatchId.generate(),
            round_id=round_id,
            match_number=match_number,
            team_a_players=tuple(team_a_players),
            team_b_players=tuple(team_b_players),
            status=MatchStatus.SCHEDULED,
            handicap_strokes_given=handicap_diff,
            strokes_given_to_team=strokes_given_to_team,
            result=None,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def reconstruct(
        cls,
        id: MatchId,
        round_id: RoundId,
        match_number: int,
        team_a_players: list[MatchPlayer],
        team_b_players: list[MatchPlayer],
        status: MatchStatus,
        handicap_strokes_given: int,
        strokes_given_to_team: str,
        result: dict | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> "Match":
        """Reconstruye desde BD (sin validaciones)."""
        return cls(
            id=id,
            round_id=round_id,
            match_number=match_number,
            team_a_players=tuple(team_a_players),
            team_b_players=tuple(team_b_players),
            status=status,
            handicap_strokes_given=handicap_strokes_given,
            strokes_given_to_team=strokes_given_to_team,
            result=result,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ==================== Business Methods ====================

    def start(self) -> None:
        """
        Inicia el partido.
        Transición: SCHEDULED → IN_PROGRESS
        """
        if not self._status.can_start():
            raise ValueError(
                f"Cannot start match from status {self._status}. "
                f"Expected SCHEDULED"
            )
        self._status = MatchStatus.IN_PROGRESS
        self._updated_at = datetime.now()

    def complete(self, result: dict) -> None:
        """
        Completa el partido con un resultado.
        Transición: IN_PROGRESS → COMPLETED

        Args:
            result: Diccionario con el resultado del partido
                   Ejemplo: {"winner": "A", "score": "3&2"}
                   o {"winner": "HALVED", "score": "AS"}
        """
        if not self._status.can_record_scores():
            raise ValueError(
                f"Cannot complete match from status {self._status}. "
                f"Expected IN_PROGRESS"
            )
        self._result = result
        self._status = MatchStatus.COMPLETED
        self._updated_at = datetime.now()

    def declare_walkover(self, winning_team: str, reason: str | None = None) -> None:
        """
        Declara walkover (victoria por incomparecencia).
        Transición: SCHEDULED o IN_PROGRESS → WALKOVER

        Args:
            winning_team: Equipo ganador ("A" o "B")
            reason: Razón del walkover (opcional)
        """
        if self._status not in (MatchStatus.SCHEDULED, MatchStatus.IN_PROGRESS):
            raise ValueError(
                f"Cannot declare walkover from status {self._status}. "
                f"Expected SCHEDULED or IN_PROGRESS"
            )

        if winning_team not in ("A", "B"):
            raise ValueError(f"winning_team must be 'A' or 'B', got '{winning_team}'")

        self._result = {
            "winner": winning_team,
            "score": "W/O",
            "reason": reason,
        }
        self._status = MatchStatus.WALKOVER
        self._updated_at = datetime.now()

    # ==================== Query Methods ====================

    def is_finished(self) -> bool:
        """Retorna True si el partido ha terminado."""
        return self._status.is_finished()

    def get_winner(self) -> str | None:
        """
        Retorna el equipo ganador ('A', 'B', 'HALVED') o None si no ha terminado.
        """
        if not self.is_finished() or self._result is None:
            return None
        return self._result.get("winner")

    def team_a_total_handicap(self) -> int:
        """Retorna el handicap combinado del Equipo A."""
        return sum(p.playing_handicap for p in self._team_a_players)

    def team_b_total_handicap(self) -> int:
        """Retorna el handicap combinado del Equipo B."""
        return sum(p.playing_handicap for p in self._team_b_players)

    # ==================== Properties ====================

    @property
    def id(self) -> MatchId:
        return self._id

    @property
    def round_id(self) -> RoundId:
        return self._round_id

    @property
    def match_number(self) -> int:
        return self._match_number

    @property
    def team_a_players(self) -> tuple[MatchPlayer, ...]:
        return self._team_a_players

    @property
    def team_b_players(self) -> tuple[MatchPlayer, ...]:
        return self._team_b_players

    @property
    def status(self) -> MatchStatus:
        return self._status

    @property
    def handicap_strokes_given(self) -> int:
        return self._handicap_strokes_given

    @property
    def strokes_given_to_team(self) -> str:
        return self._strokes_given_to_team

    @property
    def result(self) -> dict | None:
        return self._result

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ==================== Equality ====================

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Match):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return (
            f"Match(id={self._id}, "
            f"number={self._match_number}, "
            f"team_a={len(self._team_a_players)}p, "
            f"team_b={len(self._team_b_players)}p, "
            f"status={self._status})"
        )
