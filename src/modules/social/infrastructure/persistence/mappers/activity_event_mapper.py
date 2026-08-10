"""
SQLAlchemy Mapper para ActivityEvent (módulo Social).

Tabla:
- activity_events
"""

import uuid
from typing import Any

import sqlalchemy.types
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.dialects import postgresql

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.mappers.friendship_mapper import (
    SocialUserIdType,
)
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata


class ActivityEventTypeType(sqlalchemy.types.TypeDecorator[ActivityEventType]):
    """TypeDecorator para el tipo de evento."""

    impl = String(30)
    cache_ok = True

    def process_bind_param(self, value: ActivityEventType | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(
        self, value: str | None, dialect: Any
    ) -> ActivityEventType | None:
        if value is None:
            return None
        return ActivityEventType(value)


activity_events_table = Table(
    "activity_events",
    metadata,
    Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column(
        "user_id",
        SocialUserIdType,
        # Al borrar la cuenta desaparece lo que publicó: el feed no debe
        # sobrevivir a su autor
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("type", ActivityEventTypeType, nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    # El detalle de cada tipo (cuántos birdies, en qué hoyos, qué diferencial)
    # vive en JSONB en vez de en columnas: cada tipo lleva lo suyo y añadir uno
    # nuevo no debería exigir una migración
    Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
    # Sin FK: la partida puede ser rápida o de torneo, tablas distintas.
    # NOT NULL a propósito: con NULL, la clave única de abajo dejaría de proteger
    # (en Postgres un NULL nunca iguala a otro) y reprocesar duplicaría entradas
    Column("source_match_id", String(36), nullable=False),
    # El feed siempre pregunta lo mismo: los eventos de estos jugadores, del más
    # reciente al más antiguo
    Index("ix_activity_events_user_occurred", "user_id", "occurred_at"),
    # "Esta partida ya se publico?" filtra solo por partida, y el indice de
    # arriba empieza por user_id, asi que no le sirve
    Index("ix_activity_events_source_match", "source_match_id"),
    # Reprocesar una partida no debe duplicar sus entradas
    UniqueConstraint(
        "user_id", "source_match_id", "type", name="uq_activity_events_match_type"
    ),
)


def start_activity_event_mappers() -> None:
    """
    Inicia el mapeo de ActivityEvent. Idempotente de verdad.

    Se pregunta con `inspect(..., raiseerr=False)` y no con
    `ActivityEvent not in mapper_registry.mappers`: ese conjunto contiene
    objetos `Mapper`, no clases, asi que la pregunta siempre da cierto y la
    segunda llamada revienta con "already has a primary mapper defined".
    """
    if inspect(ActivityEvent, raiseerr=False) is None:
        mapper_registry.map_imperatively(
            ActivityEvent,
            activity_events_table,
            properties={
                "_id": activity_events_table.c.id,
                "_user_id": activity_events_table.c.user_id,
                "_type": activity_events_table.c.type,
                "_occurred_at": activity_events_table.c.occurred_at,
                "_payload": activity_events_table.c.payload,
                "_source_match_id": activity_events_table.c.source_match_id,
            },
        )
