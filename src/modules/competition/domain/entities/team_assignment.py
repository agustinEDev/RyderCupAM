"""
TeamAssignment Entity - Asignación de jugadores a equipos.

Representa la distribución de jugadores entre Equipo A y Equipo B.
"""

from datetime import datetime

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.user.domain.value_objects.user_id import UserId


class TeamAssignment:
    """
    Entidad que representa la asignación de equipos en una competición.

    Responsabilidades:
    - Almacenar la distribución de jugadores entre equipos
    - Validar que los equipos estén balanceados
    - Registrar el modo de asignación usado

    Características DDD:
    - Es una Entity (tiene identidad: TeamAssignmentId)
    - Vive dentro del contexto de Competition
    - Una Competition tiene una sola TeamAssignment activa
    """

    def __init__(
        self,
        id: TeamAssignmentId,
        competition_id: CompetitionId,
        mode: TeamAssignmentMode,
        team_a_player_ids: tuple[UserId, ...],
        team_b_player_ids: tuple[UserId, ...],
        created_at: datetime,
    ):
        """Constructor privado (usar factory methods)."""
        self._id = id
        self._competition_id = competition_id
        self._mode = mode
        self._team_a_player_ids = team_a_player_ids
        self._team_b_player_ids = team_b_player_ids
        self._created_at = created_at

    @classmethod
    def create(
        cls,
        competition_id: CompetitionId,
        mode: TeamAssignmentMode,
        team_a_player_ids: list[UserId],
        team_b_player_ids: list[UserId],
    ) -> "TeamAssignment":
        """
        Factory method para crear una nueva asignación.

        Business Rules:
        - Equipos deben tener igual número de jugadores
        - Ningún jugador puede estar en ambos equipos
        - Cada equipo debe tener al menos 1 jugador

        Args:
            competition_id: ID de la competición
            mode: Modo de asignación (AUTOMATIC/MANUAL)
            team_a_player_ids: IDs de jugadores del Equipo A
            team_b_player_ids: IDs de jugadores del Equipo B

        Returns:
            Nueva instancia de TeamAssignment

        Raises:
            ValueError: Si las reglas de negocio no se cumplen
        """
        # Validar equipos no vacíos
        if not team_a_player_ids or not team_b_player_ids:
            raise ValueError("Both teams must have at least one player")

        # Validar equipos balanceados
        if len(team_a_player_ids) != len(team_b_player_ids):
            raise ValueError(
                f"Teams must have equal players. "
                f"Team A: {len(team_a_player_ids)}, Team B: {len(team_b_player_ids)}"
            )

        # Validar sin duplicados entre equipos
        team_a_set = {str(uid.value) for uid in team_a_player_ids}
        team_b_set = {str(uid.value) for uid in team_b_player_ids}
        overlap = team_a_set & team_b_set
        if overlap:
            raise ValueError(f"Player(s) cannot be in both teams: {overlap}")

        # Validar sin duplicados dentro del mismo equipo
        if len(team_a_set) != len(team_a_player_ids):
            raise ValueError("Duplicate players in Team A")
        if len(team_b_set) != len(team_b_player_ids):
            raise ValueError("Duplicate players in Team B")

        return cls(
            id=TeamAssignmentId.generate(),
            competition_id=competition_id,
            mode=mode,
            team_a_player_ids=tuple(team_a_player_ids),
            team_b_player_ids=tuple(team_b_player_ids),
            created_at=datetime.now(),
        )

    @classmethod
    def reconstruct(
        cls,
        id: TeamAssignmentId,
        competition_id: CompetitionId,
        mode: TeamAssignmentMode,
        team_a_player_ids: list[UserId],
        team_b_player_ids: list[UserId],
        created_at: datetime,
    ) -> "TeamAssignment":
        """Reconstruye desde BD (sin validaciones)."""
        return cls(
            id=id,
            competition_id=competition_id,
            mode=mode,
            team_a_player_ids=tuple(team_a_player_ids),
            team_b_player_ids=tuple(team_b_player_ids),
            created_at=created_at,
        )

    # ==================== Query Methods ====================

    def is_player_in_team_a(self, user_id: UserId) -> bool:
        """Verifica si un jugador está en el Equipo A."""
        return user_id in self._team_a_player_ids

    def is_player_in_team_b(self, user_id: UserId) -> bool:
        """Verifica si un jugador está en el Equipo B."""
        return user_id in self._team_b_player_ids

    def get_player_team(self, user_id: UserId) -> str | None:
        """
        Retorna el equipo del jugador ('A', 'B', o None si no está).
        """
        if self.is_player_in_team_a(user_id):
            return "A"
        if self.is_player_in_team_b(user_id):
            return "B"
        return None

    def total_players(self) -> int:
        """Retorna el total de jugadores asignados."""
        return len(self._team_a_player_ids) + len(self._team_b_player_ids)

    def players_per_team(self) -> int:
        """Retorna el número de jugadores por equipo."""
        return len(self._team_a_player_ids)

    # ==================== Properties ====================

    @property
    def id(self) -> TeamAssignmentId:
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        return self._competition_id

    @property
    def mode(self) -> TeamAssignmentMode:
        return self._mode

    @property
    def team_a_player_ids(self) -> tuple[UserId, ...]:
        return self._team_a_player_ids

    @property
    def team_b_player_ids(self) -> tuple[UserId, ...]:
        return self._team_b_player_ids

    @property
    def created_at(self) -> datetime:
        return self._created_at

    # ==================== Equality ====================

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TeamAssignment):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return (
            f"TeamAssignment(id={self._id}, "
            f"mode={self._mode}, "
            f"team_a={len(self._team_a_player_ids)}, "
            f"team_b={len(self._team_b_player_ids)})"
        )
