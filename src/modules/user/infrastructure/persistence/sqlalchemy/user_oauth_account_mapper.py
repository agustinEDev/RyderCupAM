"""
User OAuth Account Mapper - Infrastructure Layer

Mapeo imperativo entre la entidad UserOAuthAccount y la tabla user_oauth_accounts.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, UniqueConstraint, inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_account_id import OAuthAccountId
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)


# --- TypeDecorator para OAuthAccountId ---
class OAuthAccountIdDecorator(TypeDecorator):
    """TypeDecorator para OAuthAccountId como CHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: OAuthAccountId | str, dialect) -> str | None:
        if isinstance(value, OAuthAccountId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str, dialect) -> OAuthAccountId | None:
        if value is None:
            return None
        return OAuthAccountId(uuid.UUID(value))


# --- TypeDecorator para UserId ---
class UserIdDecorator(TypeDecorator):
    """TypeDecorator para UserId como CHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | str, dialect) -> str | None:
        if isinstance(value, UserId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str, dialect) -> UserId | None:
        if value is None:
            return None
        return UserId(uuid.UUID(value))


# --- TypeDecorator para OAuthProvider ---
class OAuthProviderDecorator(TypeDecorator):
    """TypeDecorator para OAuthProvider enum como String."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: OAuthProvider | str, dialect) -> str | None:
        if isinstance(value, OAuthProvider):
            return value.value
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str, dialect) -> OAuthProvider | None:
        if value is None:
            return None
        return OAuthProvider(value)


# --- Definición de la Tabla ---
user_oauth_accounts_table = Table(
    "user_oauth_accounts",
    metadata,
    Column("id", OAuthAccountIdDecorator, primary_key=True),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("provider", OAuthProviderDecorator, nullable=False),
    Column("provider_user_id", String(255), nullable=False),
    Column("provider_email", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False),
    # Unique constraint: una cuenta de proveedor solo puede vincularse una vez
    UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    # Index para búsquedas por user_id
    Index("ix_oauth_accounts_user_id", "user_id"),
)


def start_oauth_account_mappers():
    """
    Inicia el mapeo entre UserOAuthAccount y user_oauth_accounts table.
    Idempotente.
    """
    try:
        inspect(UserOAuthAccount)
    except NoInspectionAvailable:
        mapper_registry.map_imperatively(
            UserOAuthAccount,
            user_oauth_accounts_table,
            properties={},
        )
