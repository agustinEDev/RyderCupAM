"""
QuickMatchHoleScore Entity - Score de un participante en un hoyo de una partida rapida.

Modelo simple (v1): un unico score por participante y hoyo, sin validacion dual
jugador/marcador (a diferencia de HoleScore en el modulo competition). Se
registra ademas quien lo introdujo (`recorded_by_participant_id`), ya que un
anotador puede registrar el score de otro participante (invitado o registrado
que no esta anotando en esta partida).
"""

from datetime import datetime

from ..exceptions.quick_match_violations import InvalidHoleScoreViolation
from ..value_objects.participant_id import ParticipantId
from ..value_objects.quick_match_hole_score_id import QuickMatchHoleScoreId
from ..value_objects.quick_match_id import QuickMatchId

MIN_SCORE = 1
MAX_SCORE = 15
MIN_HOLE_NUMBER = 1
MAX_HOLE_NUMBER = 18


class QuickMatchHoleScore:
    """
    Entidad QuickMatchHoleScore - Score de un participante en un hoyo concreto.

    Invariantes:
    - hole_number entre 1 y 18
    - score entre 1 y 15 (mismo rango que HoleScore en competition)
    """

    def __init__(
        self,
        id: QuickMatchHoleScoreId,
        quick_match_id: QuickMatchId,
        hole_number: int,
        participant_id: ParticipantId,
        score: int,
        recorded_by_participant_id: ParticipantId,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self._validate_hole_number(hole_number)
        self._validate_score(score)

        self._id = id
        self._quick_match_id = quick_match_id
        self._hole_number = hole_number
        self._participant_id = participant_id
        self._score = score
        self._recorded_by_participant_id = recorded_by_participant_id
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()

    @staticmethod
    def _validate_hole_number(hole_number: int) -> None:
        if not (MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER):
            raise InvalidHoleScoreViolation(
                f"hole_number debe estar entre {MIN_HOLE_NUMBER} y {MAX_HOLE_NUMBER}."
            )

    @staticmethod
    def _validate_score(score: int) -> None:
        if not (MIN_SCORE <= score <= MAX_SCORE):
            raise InvalidHoleScoreViolation(f"score debe estar entre {MIN_SCORE} y {MAX_SCORE}.")

    # ===========================================
    # FACTORY METHODS
    # ===========================================

    @classmethod
    def create(
        cls,
        id: QuickMatchHoleScoreId,
        quick_match_id: QuickMatchId,
        hole_number: int,
        participant_id: ParticipantId,
        score: int,
        recorded_by_participant_id: ParticipantId,
    ) -> "QuickMatchHoleScore":
        now = datetime.now()
        return cls(
            id=id,
            quick_match_id=quick_match_id,
            hole_number=hole_number,
            participant_id=participant_id,
            score=score,
            recorded_by_participant_id=recorded_by_participant_id,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def reconstruct(
        cls,
        id: QuickMatchHoleScoreId,
        quick_match_id: QuickMatchId,
        hole_number: int,
        participant_id: ParticipantId,
        score: int,
        recorded_by_participant_id: ParticipantId,
        created_at: datetime,
        updated_at: datetime,
    ) -> "QuickMatchHoleScore":
        return cls(
            id=id,
            quick_match_id=quick_match_id,
            hole_number=hole_number,
            participant_id=participant_id,
            score=score,
            recorded_by_participant_id=recorded_by_participant_id,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ===========================================
    # PROPERTIES
    # ===========================================

    @property
    def id(self) -> QuickMatchHoleScoreId:
        return self._id

    @property
    def quick_match_id(self) -> QuickMatchId:
        return self._quick_match_id

    @property
    def hole_number(self) -> int:
        return self._hole_number

    @property
    def participant_id(self) -> ParticipantId:
        return self._participant_id

    @property
    def score(self) -> int:
        return self._score

    @property
    def recorded_by_participant_id(self) -> ParticipantId:
        return self._recorded_by_participant_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # METODOS DE COMANDO
    # ===========================================

    def update_score(self, score: int, recorded_by_participant_id: ParticipantId) -> None:
        """Actualiza el score (upsert desde el use case)."""
        self._validate_score(score)
        self._score = score
        self._recorded_by_participant_id = recorded_by_participant_id
        self._updated_at = datetime.now()

    # ===========================================
    # METODOS ESPECIALES
    # ===========================================

    def __eq__(self, other) -> bool:
        return isinstance(other, QuickMatchHoleScore) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
