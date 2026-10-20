"""
Terms Acceptance Mapper - Infrastructure Layer

Mapeo imperativo entre TermsAcceptance y la tabla terms_acceptances.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.terms_acceptance import (
    IP_ADDRESS_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    TermsAcceptance,
)
from src.modules.user.domain.services.terms_of_service import TERMS_VERSION_MAX_LENGTH
from src.modules.user.domain.value_objects.terms_acceptance_id import TermsAcceptanceId
from src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper import (
    UserIdDecorator,
)
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)


class TermsAcceptanceIdDecorator(TypeDecorator):
    """TermsAcceptanceId como CHAR(36) en BD."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: TermsAcceptanceId | str | None, dialect) -> str | None:
        if isinstance(value, TermsAcceptanceId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> TermsAcceptanceId | None:
        if value is None:
            return None
        return TermsAcceptanceId(uuid.UUID(value))


# Historial de solo inserción. ON DELETE CASCADE, como el resto de lo que
# cuelga de un usuario: si se borra la cuenta, se va con ella
terms_acceptances_table = Table(
    "terms_acceptances",
    metadata,
    Column("id", TermsAcceptanceIdDecorator, primary_key=True),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("terms_version", String(TERMS_VERSION_MAX_LENGTH), nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=False),
    Column("ip_address", String(IP_ADDRESS_MAX_LENGTH), nullable=True),
    Column("user_agent", String(USER_AGENT_MAX_LENGTH), nullable=True),
)

Index("ix_terms_acceptances_user_id", terms_acceptances_table.c.user_id)


def start_mappers():
    """Mapea TermsAcceptance a terms_acceptances. Idempotente."""
    try:
        inspect(TermsAcceptance)
    except NoInspectionAvailable:
        mapper_registry.map_imperatively(
            TermsAcceptance,
            terms_acceptances_table,
            properties={
                "_id": terms_acceptances_table.c.id,
                "_user_id": terms_acceptances_table.c.user_id,
                "_terms_version": terms_acceptances_table.c.terms_version,
                "_accepted_at": terms_acceptances_table.c.accepted_at,
                "_ip_address": terms_acceptances_table.c.ip_address,
                "_user_agent": terms_acceptances_table.c.user_agent,
            },
        )
