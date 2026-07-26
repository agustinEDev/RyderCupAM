"""DTOs para el modulo QuickMatch."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateQuickMatchRequestDTO(BaseModel):
    """DTO para crear una partida rapida."""

    creator_id: UUID
    golf_course_id: UUID
    match_format: str = Field(..., pattern="^(SINGLES|FOURBALL|FOURSOMES)$")


class AddParticipantRequestDTO(BaseModel):
    """DTO para añadir un amigo como participante."""

    quick_match_id: UUID
    requester_id: UUID
    friend_user_id: UUID
    team: str | None = Field(None, pattern="^(A|B)$")


class RemoveParticipantRequestDTO(BaseModel):
    """DTO para eliminar un participante (leave o kick por el creador)."""

    quick_match_id: UUID
    requester_id: UUID
    target_user_id: UUID


class SubmitHoleScoreRequestDTO(BaseModel):
    """DTO para registrar/actualizar el score propio de un hoyo."""

    quick_match_id: UUID
    player_user_id: UUID
    hole_number: int = Field(..., ge=1, le=18)
    score: int = Field(..., ge=1, le=15)


class QuickMatchParticipantDTO(BaseModel):
    """DTO de un participante enriquecido con su nombre."""

    user_id: UUID
    name: str
    team: str | None = None


class QuickMatchResponseDTO(BaseModel):
    """DTO de respuesta completa de una partida rapida."""

    id: UUID
    creator_id: UUID
    golf_course_id: UUID
    match_format: str
    status: str
    participants: list[QuickMatchParticipantDTO]
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
    player_user_id: UUID
    score: int


class QuickMatchStandingResponseDTO(BaseModel):
    """DTO del estado del partido calculado a partir de los scores registrados."""

    status: str
    leading_team: str | None = None
    holes_played: int
    holes_remaining: int
    is_decided: bool


class QuickMatchDetailResponseDTO(QuickMatchResponseDTO):
    """DTO de detalle: partida + scores + standing calculado."""

    hole_scores: list[HoleScoreResponseDTO]
    standing: QuickMatchStandingResponseDTO | None = None
