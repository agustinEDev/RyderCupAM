"""
Terms Acceptance Mapper - Infrastructure Layer

Mapeo imperativo entre TermsAcceptance y la tabla terms_acceptances.
"""

import uuid

from sqlalchemy import (
    DDL,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.types import CHAR, TypeDecorator

from src.modules.user.domain.entities.terms_acceptance import (
    IP_ADDRESS_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    USER_EMAIL_MAX_LENGTH,
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


# Historial que sobrevive al borrado de la cuenta (TERMS_ACCEPTANCE_RETENTION_YEARS):
# ON DELETE SET NULL, con el email guardado en la fila y user_deleted_at, que
# rellena el trigger BEFORE DELETE ON users (abajo). Una versión, una fila por usuario: el
# UNIQUE es defensa en profundidad (tras borrar, user_id es NULL y los NULL no
# chocan entre sí)
terms_acceptances_table = Table(
    "terms_acceptances",
    metadata,
    Column("id", TermsAcceptanceIdDecorator, primary_key=True),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("user_email", String(USER_EMAIL_MAX_LENGTH), nullable=False),
    Column("terms_version", String(TERMS_VERSION_MAX_LENGTH), nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=False),
    Column("ip_address", String(IP_ADDRESS_MAX_LENGTH), nullable=True),
    Column("user_agent", String(USER_AGENT_MAX_LENGTH), nullable=True),
    Column("user_deleted_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("user_id", "terms_version", name="uq_terms_acceptances_user_version"),
)

# Sin índice propio por user_id: el UNIQUE (user_id, terms_version) ya lo cubre.
Index("ix_terms_acceptances_user_deleted_at", terms_acceptances_table.c.user_deleted_at)

# Al borrar un usuario, por el camino que sea (el admin, un script, un DELETE a
# mano), sus aceptaciones se fechan: sin user_deleted_at, la purga de los 3
# años no las encontraría nunca. Lo hace la base de datos, como el SET NULL de
# la FK, para que no dependa de que cada camino de borrado se acuerde. Va en
# los METADATOS además de en la migración (e7f9a1b3c5d7), porque el esquema de
# los tests se construye con `metadata.create_all`; las dos copias tienen que
# coincidir (lo comprueba tests/integration/test_schema_parity.py)
MARK_USER_DELETED_FUNCTION = """
CREATE OR REPLACE FUNCTION terms_acceptances_mark_user_deleted() RETURNS trigger AS $$
BEGIN
    UPDATE terms_acceptances SET user_deleted_at = now()
    WHERE user_id = OLD.id AND user_deleted_at IS NULL;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql
"""
MARK_USER_DELETED_TRIGGER = """
CREATE TRIGGER trg_users_mark_terms_acceptances_deleted
BEFORE DELETE ON users
FOR EACH ROW EXECUTE FUNCTION terms_acceptances_mark_user_deleted()
"""

event.listen(
    terms_acceptances_table,
    "after_create",
    DDL(MARK_USER_DELETED_FUNCTION).execute_if(dialect="postgresql"),
)
event.listen(
    terms_acceptances_table,
    "after_create",
    DDL(MARK_USER_DELETED_TRIGGER).execute_if(dialect="postgresql"),
)


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
                "_user_email": terms_acceptances_table.c.user_email,
                "_user_deleted_at": terms_acceptances_table.c.user_deleted_at,
                "_terms_version": terms_acceptances_table.c.terms_version,
                "_accepted_at": terms_acceptances_table.c.accepted_at,
                "_ip_address": terms_acceptances_table.c.ip_address,
                "_user_agent": terms_acceptances_table.c.user_agent,
            },
        )
