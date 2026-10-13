"""DTOs para el modulo Social (Friendship)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SendFriendRequestRequestDTO(BaseModel):
    """DTO para enviar una solicitud de amistad."""

    requester_id: UUID
    addressee_id: UUID


class RespondFriendRequestRequestDTO(BaseModel):
    """DTO para responder a una solicitud de amistad."""

    friendship_id: UUID
    user_id: UUID
    action: str  # "ACCEPT" or "DECLINE"


class FriendshipResponseDTO(BaseModel):
    """DTO de respuesta con shape completa del contrato frontend."""

    id: UUID
    requester_id: UUID
    requester_name: str
    addressee_id: UUID
    addressee_name: str
    status: str
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # El hándicap de cada lado, solo en la lista de amigos: el asistente de
    # partida rápida lo enseña antes de crear nada (FE #848). Nulo si no tiene
    requester_handicap: float | None = None
    addressee_handicap: float | None = None


class PaginatedFriendshipResponseDTO(BaseModel):
    """DTO paginado de relaciones de amistad."""

    friendships: list[FriendshipResponseDTO]
    total_count: int
    page: int
    limit: int
