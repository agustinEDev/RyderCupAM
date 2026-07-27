"""DTOs para el modulo QuickMatch."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.quick_match.domain.entities.quick_match import MAX_NAME_LENGTH, MAX_SCORERS


class CreateQuickMatchRequestDTO(BaseModel):
    """DTO para crear una partida rapida."""

    creator_id: UUID
    golf_course_id: UUID
    match_format: str = Field(..., pattern="^(SINGLES|FOURBALL|FOURSOMES)$")
    name: str | None = Field(
        None, max_length=MAX_NAME_LENGTH, description="Nombre opcional para diferenciar la partida"
    )


class AddParticipantRequestDTO(BaseModel):
    """DTO para añadir un amigo registrado como participante."""

    quick_match_id: UUID
    requester_id: UUID
    friend_user_id: UUID
    team: str | None = Field(None, pattern="^(A|B)$")


class AddGuestParticipantRequestDTO(BaseModel):
    """DTO para añadir a mano un jugador invitado (sin cuenta) como participante."""

    quick_match_id: UUID
    requester_id: UUID
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    handicap: float | None = Field(None, ge=-10.0, le=54.0)
    team: str | None = Field(None, pattern="^(A|B)$")


class RemoveParticipantRequestDTO(BaseModel):
    """DTO para eliminar un participante (leave o kick por el creador)."""

    quick_match_id: UUID
    requester_id: UUID
    target_participant_id: UUID


class StartQuickMatchRequestDTO(BaseModel):
    """DTO para iniciar la partida, configurando quien anota (1 a 4 anotadores)."""

    quick_match_id: UUID
    requester_id: UUID
    scorer_ids: list[UUID] = Field(..., min_length=1, max_length=MAX_SCORERS)


class SubmitHoleScoreRequestDTO(BaseModel):
    """DTO para registrar/actualizar el score propio de un hoyo (solo anotadores)."""

    quick_match_id: UUID
    player_user_id: UUID
    hole_number: int = Field(..., ge=1, le=18)
    score: int = Field(..., ge=1, le=15)


class SubmitProxyHoleScoreRequestDTO(BaseModel):
    """DTO para que un anotador registre el score de otro participante asignado."""

    quick_match_id: UUID
    scorer_user_id: UUID
    target_participant_id: UUID
    hole_number: int = Field(..., ge=1, le=18)
    score: int = Field(..., ge=1, le=15)


class QuickMatchParticipantDTO(BaseModel):
    """DTO de un participante enriquecido con su nombre."""

    participant_id: UUID
    user_id: UUID | None = None
    name: str
    handicap: float | None = None
    team: str | None = None
    is_guest: bool = False


class QuickMatchResponseDTO(BaseModel):
    """DTO de respuesta completa de una partida rapida."""

    id: UUID
    creator_id: UUID
    golf_course_id: UUID
    match_format: str
    status: str
    name: str | None = None
    participants: list[QuickMatchParticipantDTO]
    scorer_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class PaginatedQuickMatchResponseDTO(BaseModel):
    """DTO paginado de partidas rapidas."""

    quick_matches: list[QuickMatchResponseDTO]
    total_count: int
    page: int
    limit: int


class HoleScoreResponseDTO(BaseModel):
    """DTO de un score de hoyo registrado."""

    hole_number: int
    participant_id: UUID
    score: int
    recorded_by_participant_id: UUID


class QuickMatchStandingResponseDTO(BaseModel):
    """DTO del estado del partido calculado a partir de los scores registrados."""

    status: str
    leading_team: str | None = None
    holes_played: int
    holes_remaining: int
    is_decided: bool


class ScoringAssignmentDTO(BaseModel):
    """DTO del reparto de anotacion: que participantes cubre cada anotador."""

    scorer_participant_id: UUID
    scorer_name: str
    covered_participant_ids: list[UUID]


class QuickMatchDetailResponseDTO(QuickMatchResponseDTO):
    """DTO de detalle: partida + scores + standing + reparto de anotacion."""

    hole_scores: list[HoleScoreResponseDTO]
    standing: QuickMatchStandingResponseDTO | None = None
    scoring_assignments: list[ScoringAssignmentDTO] = Field(default_factory=list)
