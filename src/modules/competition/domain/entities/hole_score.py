"""
HoleScore Entity - Score de un jugador en un hoyo especifico.

Representa el registro de score de un jugador en un hoyo, incluyendo
la validacion cruzada con el marcador asignado.
"""

from datetime import datetime

from src.modules.competition.domain.value_objects.hole_score_id import HoleScoreId
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId

MIN_SCORE = 1
MAX_SCORE = 9
MIN_HOLE = 1
MAX_HOLE = 18


class HoleScore:
    """
    Entidad que representa el score de un jugador en un hoyo.

    Gestiona:
    - Registro del score propio (own_score) por parte del jugador
    - Registro del score del marcador (marker_score)
    - Validacion cruzada automatica (PENDING/MATCH/MISMATCH)
    - Calculo de net score (score - strokes_received)

    Invariantes:
    - hole_number debe estar entre 1 y 18
    - team debe ser "A" o "B"
    - Scores deben estar entre 1-9 o None (picked up)
    - strokes_received debe ser >= 0 (normalmente 0-2, puede ser > 1 si PH > 18)
    """

    def __init__(
        self,
        id: HoleScoreId,
        match_id: MatchId,
        hole_number: int,
        player_user_id: UserId,
        team: str,
        own_score: int | None,
        own_submitted: bool,
        marker_score: int | None,
        marker_submitted: bool,
        strokes_received: int,
        net_score: int | None,
        validation_status: ValidationStatus,
        created_at: datetime,
        updated_at: datetime,
    ):
        """Constructor privado (usar factory methods)."""
        self._id = id
        self._match_id = match_id
        self._hole_number = hole_number
        self._player_user_id = player_user_id
        self._team = team
        self._own_score = own_score
        self._own_submitted = own_submitted
        self._marker_score = marker_score
        self._marker_submitted = marker_submitted
        self._strokes_received = strokes_received
        self._net_score = net_score
        self._validation_status = validation_status
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def create(
        cls,
        match_id: MatchId,
        hole_number: int,
        player_user_id: UserId,
        team: str,
        strokes_received: int,
    ) -> "HoleScore":
        """
        Factory method para crear un HoleScore vacio (pre-creacion al START).

        Args:
            match_id: ID del partido
            hole_number: Numero de hoyo (1-18)
            player_user_id: ID del jugador
            team: Equipo ("A" o "B")
            strokes_received: Golpes que recibe en este hoyo (>= 0, normalmente 0-2)

        Raises:
            ValueError: Si hole_number, team o strokes_received son invalidos
        """
        if not MIN_HOLE <= hole_number <= MAX_HOLE:
            raise ValueError(f"hole_number must be between {MIN_HOLE} and {MAX_HOLE}, got {hole_number}")

        if team not in ("A", "B"):
            raise ValueError(f"team must be 'A' or 'B', got '{team}'")

        if strokes_received < 0:
            raise ValueError(f"strokes_received must be >= 0, got {strokes_received}")

        now = datetime.now()
        return cls(
            id=HoleScoreId.generate(),
            match_id=match_id,
            hole_number=hole_number,
            player_user_id=player_user_id,
            team=team,
            own_score=None,
            own_submitted=False,
            marker_score=None,
            marker_submitted=False,
            strokes_received=strokes_received,
            net_score=None,
            validation_status=ValidationStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def reconstruct(
        cls,
        id: HoleScoreId,
        match_id: MatchId,
        hole_number: int,
        player_user_id: UserId,
        team: str,
        own_score: int | None,
        own_submitted: bool,
        marker_score: int | None,
        marker_submitted: bool,
        strokes_received: int,
        net_score: int | None,
        validation_status: ValidationStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> "HoleScore":
        """Reconstruye desde BD (sin validaciones)."""
        return cls(
            id=id,
            match_id=match_id,
            hole_number=hole_number,
            player_user_id=player_user_id,
            team=team,
            own_score=own_score,
            own_submitted=own_submitted,
            marker_score=marker_score,
            marker_submitted=marker_submitted,
            strokes_received=strokes_received,
            net_score=net_score,
            validation_status=validation_status,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ==================== Business Methods ====================

    def set_own_score(self, score: int | None) -> None:
        """
        Registra el score del jugador para este hoyo.

        Args:
            score: Score del jugador (1-9) o None (picked up)

        Raises:
            ValueError: Si el score esta fuera del rango 1-9
        """
        if score is not None and not MIN_SCORE <= score <= MAX_SCORE:
            raise ValueError(f"Score must be between {MIN_SCORE} and {MAX_SCORE}, got {score}")

        self._own_score = score
        self._own_submitted = True
        self._updated_at = datetime.now()

    def set_marker_score(self, score: int | None) -> None:
        """
        Registra el score asignado por el marcador para este hoyo.

        Args:
            score: Score del marcador (1-9) o None (picked up)

        Raises:
            ValueError: Si el score esta fuera del rango 1-9
        """
        if score is not None and not MIN_SCORE <= score <= MAX_SCORE:
            raise ValueError(f"Score must be between {MIN_SCORE} and {MAX_SCORE}, got {score}")

        self._marker_score = score
        self._marker_submitted = True
        self._updated_at = datetime.now()

    def recalculate_validation(self) -> None:
        """
        Recalcula el validation_status basado en own_score y marker_score.

        Reglas:
        - Si falta alguno de los dos → PENDING
        - Si ambos coinciden (incl. None == None) → MATCH
        - Si difieren (incl. None vs numero) → MISMATCH
        """
        if not self._own_submitted or not self._marker_submitted:
            self._validation_status = ValidationStatus.PENDING
        elif self._own_score == self._marker_score:
            self._validation_status = ValidationStatus.MATCH
        else:
            self._validation_status = ValidationStatus.MISMATCH

        self._calculate_net_score()
        self._updated_at = datetime.now()

    def _calculate_net_score(self) -> None:
        """
        Calcula el net score si el estado es MATCH y hay score.

        Net = own_score - strokes_received (minimo 0).
        Si picked up (own_score es None): net_score = None.
        """
        if self._validation_status == ValidationStatus.MATCH and self._own_score is not None:
            self._net_score = max(0, self._own_score - self._strokes_received)
        else:
            self._net_score = None

    # ==================== Properties ====================

    @property
    def id(self) -> HoleScoreId:
        return self._id

    @property
    def match_id(self) -> MatchId:
        return self._match_id

    @property
    def hole_number(self) -> int:
        return self._hole_number

    @property
    def player_user_id(self) -> UserId:
        return self._player_user_id

    @property
    def team(self) -> str:
        return self._team

    @property
    def own_score(self) -> int | None:
        return self._own_score

    @property
    def own_submitted(self) -> bool:
        return self._own_submitted

    @property
    def marker_score(self) -> int | None:
        return self._marker_score

    @property
    def marker_submitted(self) -> bool:
        return self._marker_submitted

    @property
    def strokes_received(self) -> int:
        return self._strokes_received

    @property
    def net_score(self) -> int | None:
        return self._net_score

    @property
    def validation_status(self) -> ValidationStatus:
        return self._validation_status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ==================== Equality ====================

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HoleScore):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return (
            f"HoleScore(id={self._id}, "
            f"match={self._match_id}, "
            f"hole={self._hole_number}, "
            f"player={self._player_user_id}, "
            f"own={self._own_score}, "
            f"marker={self._marker_score}, "
            f"status={self._validation_status})"
        )
