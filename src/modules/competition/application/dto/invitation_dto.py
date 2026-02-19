"""DTOs para el modulo de invitaciones."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SendInvitationByUserIdRequestDTO(BaseModel):
    """DTO para enviar invitacion por user_id."""

    competition_id: UUID
    inviter_id: UUID
    invitee_user_id: UUID
    personal_message: str | None = Field(None, max_length=500)


class SendInvitationByEmailRequestDTO(BaseModel):
    """DTO para enviar invitacion por email."""

    competition_id: UUID
    inviter_id: UUID
    invitee_email: str
    personal_message: str | None = Field(None, max_length=500)


class RespondInvitationRequestDTO(BaseModel):
    """DTO para responder a una invitacion."""

    invitation_id: UUID
    user_id: UUID
    action: str  # "ACCEPT" or "DECLINE"


class InvitationResponseDTO(BaseModel):
    """DTO de respuesta con shape completa del contrato frontend."""

    id: UUID
    competition_id: UUID
    competition_name: str
    inviter_id: UUID
    inviter_name: str
    invitee_email: str
    invitee_user_id: UUID | None = None
    invitee_name: str | None = None
    status: str
    personal_message: str | None = None
    expires_at: datetime
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RespondInvitationResponseDTO(BaseModel):
    """DTO de respuesta al responder a una invitacion."""

    id: UUID
    competition_id: UUID
    competition_name: str
    inviter_id: UUID
    inviter_name: str
    invitee_email: str
    invitee_user_id: UUID | None = None
    invitee_name: str | None = None
    status: str
    personal_message: str | None = None
    expires_at: datetime
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    enrollment_id: UUID | None = None


class PaginatedInvitationResponseDTO(BaseModel):
    """DTO paginado de invitaciones."""

    invitations: list[InvitationResponseDTO]
    total_count: int
    page: int
    limit: int
