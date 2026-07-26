"""
SQLAlchemy Mapper for Friendship aggregate (Social module).

Tabla:
- friendships (agregado raiz)
"""

import uuid
from typing import Any

import sqlalchemy.types
from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import CHAR

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata

# ============================================================================
# TypeDecorators for Value Objects (MUST be before tables)
# ============================================================================


class FriendshipIdType(sqlalchemy.types.TypeDecorator[FriendshipId]):
    """TypeDecorator para FriendshipId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: FriendshipId | None, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value.value

    def process_result_value(
        self, value: uuid.UUID | None, dialect: Any
    ) -> FriendshipId | None:
        if value is None:
            return None
        return FriendshipId(value)


class SocialUserIdType(sqlalchemy.types.TypeDecorator[UserId]):
    """TypeDecorator para UserId Value Object (compatible con users.id CHAR(36))."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value.value)

    def process_result_value(self, value: str | None, dialect: Any) -> UserId | None:
        if value is None:
            return None
        return UserId(uuid.UUID(value))


class FriendshipStatusType(sqlalchemy.types.TypeDecorator[FriendshipStatus]):
    """TypeDecorator para FriendshipStatus Value Object."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: FriendshipStatus | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(
        self, value: str | None, dialect: Any
    ) -> FriendshipStatus | None:
        if value is None:
            return None
        return FriendshipStatus(value)


# ============================================================================
# TABLA FRIENDSHIPS
# ============================================================================

friendships_table = Table(
    "friendships",
    metadata,
    Column("id", FriendshipIdType, primary_key=True),
    Column(
        "requester_id",
        SocialUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "addressee_id",
        SocialUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", FriendshipStatusType, nullable=False),
    Column(
        "blocked_by",
        SocialUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("responded_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


def start_social_mappers() -> None:
    """
    Inicia el mapeo entre entidades del modulo Social y tablas de BD.

    Es idempotente: puede llamarse multiples veces sin efectos adversos.

    Mapea:
    - Friendship entity -> friendships table
    """
    if Friendship not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Friendship,
            friendships_table,
            properties={
                "_id": friendships_table.c.id,
                "_requester_id": friendships_table.c.requester_id,
                "_addressee_id": friendships_table.c.addressee_id,
                "_status": friendships_table.c.status,
                "_blocked_by": friendships_table.c.blocked_by,
                "_responded_at": friendships_table.c.responded_at,
                "_created_at": friendships_table.c.created_at,
                "_updated_at": friendships_table.c.updated_at,
            },
        )
