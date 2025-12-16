"""
SQLAlchemy Imperative Mapping para RefreshToken.

Mapea la entidad RefreshToken a la tabla refresh_tokens usando Imperative Mapping.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, MetaData, String, Table, TypeDecorator
from sqlalchemy.orm import registry, relationship

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.token_hash import TokenHash
from src.modules.user.domain.value_objects.user_id import UserId

# Registry para imperative mapping
mapper_registry = registry()
metadata = MetaData()

# ============================================================================
# TypeDecorators para Value Objects
# ============================================================================


class RefreshTokenIdDecorator(TypeDecorator):
    """TypeDecorator para RefreshTokenId."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convierte RefreshTokenId → string para BD."""
        if isinstance(value, RefreshTokenId):
            return str(value.value)
        return value

    def process_result_value(self, value, dialect):
        """Convierte string → RefreshTokenId desde BD."""
        if value is None:
            return None
        return RefreshTokenId(value)


class UserIdDecorator(TypeDecorator):
    """TypeDecorator para UserId."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convierte UserId → string para BD."""
        if isinstance(value, UserId):
            return str(value.value)
        return value

    def process_result_value(self, value, dialect):
        """Convierte string → UserId desde BD."""
        if value is None:
            return None
        return UserId(value)


class TokenHashDecorator(TypeDecorator):
    """TypeDecorator para TokenHash."""
    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convierte TokenHash → string para BD."""
        if isinstance(value, TokenHash):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        """Convierte string → TokenHash desde BD."""
        if value is None:
            return None
        return TokenHash(value)


# ============================================================================
# Tabla refresh_tokens
# ============================================================================

refresh_tokens_table = Table(
    "refresh_tokens",
    metadata,
    Column("id", RefreshTokenIdDecorator, primary_key=True),
    Column("user_id", UserIdDecorator, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("token_hash", TokenHashDecorator, nullable=False, unique=True, index=True),
    Column("expires_at", DateTime, nullable=False, index=True),
    Column("created_at", DateTime, nullable=False),
    Column("revoked", Boolean, nullable=False, default=False),
    Column("revoked_at", DateTime, nullable=True),
)


# ============================================================================
# Mapper de RefreshToken Entity
# ============================================================================

def start_mappers():
    """
    Configura el imperative mapping de RefreshToken.

    Debe ser llamado al inicio de la aplicación (main.py).
    """
    mapper_registry.map_imperatively(
        RefreshToken,
        refresh_tokens_table,
        properties={
            "_id": refresh_tokens_table.c.id,
            "_user_id": refresh_tokens_table.c.user_id,
            "_token_hash": refresh_tokens_table.c.token_hash,
            "_expires_at": refresh_tokens_table.c.expires_at,
            "_created_at": refresh_tokens_table.c.created_at,
            "_revoked": refresh_tokens_table.c.revoked,
            "_revoked_at": refresh_tokens_table.c.revoked_at,
        },
    )
