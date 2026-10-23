"""
SQLAlchemy Mapper para ActivityEvent (módulo Social).

Tabla:
- activity_events
"""

import uuid
from typing import Any

import sqlalchemy.types
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    inspect,
    text,
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

    def process_result_value(self, value: str | None, dialect: Any) -> ActivityEventType | None:
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
    # Cuando llego al feed, que no es cuando se jugo: un torneo publica al
    # cerrarse vueltas de hace dias. El feed se ordena y el aviso cuenta por
    # esta. En UTC sin zona; el valor por defecto cubre al codigo viejo que
    # siga insertando durante el despliegue
    Column(
        "published_at",
        DateTime,
        nullable=False,
        server_default=text("timezone('utc', now())"),
    ),
    # Con la publicacion apagada el logro se guarda solo para su autor, y
    # encenderla despues no lo destapa
    Column("visible_to_friends", Boolean, nullable=False, server_default=text("true")),
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
    UniqueConstraint("user_id", "source_match_id", "type", name="uq_activity_events_match_type"),
)

# Quien perdio su aviso de salida de una ronda por un cambio en ella (se quedo
# sin partido o sin grupo) y aun no lo ha recuperado: si vuelve a tener salida
# en esa ronda, su aviso nuevo es un cambio (prueba de punta a punta del 22 oct
# 2026: reasignar rivales de la Ryder son dos pasos). Una fila por (jugador,
# ronda); el torneo, para olvidarlas todas con una baja o una cancelacion
withdrawn_tee_time_notices_table = Table(
    "withdrawn_tee_time_notices",
    metadata,
    Column(
        "user_id",
        SocialUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # Sin FK, como `source_match_id`: la ronda es de otro modulo
    Column("round_id", String(36), primary_key=True),
    Column("competition_id", String(36), nullable=False),
    Column(
        "withdrawn_at",
        DateTime,
        nullable=False,
        server_default=text("timezone('utc', now())"),
    ),
    Index("ix_withdrawn_tee_time_notices_round", "round_id"),
    Index("ix_withdrawn_tee_time_notices_competition", "competition_id"),
)

# Los logros que se publicaron ocultos (con la publicacion apagada) y se
# retiraron: al reabrir el torneo, o al llevarse otro mas antiguo «campo nuevo»
# o «primer torneo». Si el mismo logro —jugador, tipo y origen— se vuelve a
# publicar, vuelve oculto aunque ahora este encendida: encenderla no destapa
# nada (fallo del probador, 23 oct 2026). La fila se gasta al volver a publicar
# el logro, que desde entonces guarda el mismo lo oculto
withdrawn_hidden_achievements_table = Table(
    "withdrawn_hidden_achievements",
    metadata,
    Column(
        "user_id",
        SocialUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("source_match_id", String(36), primary_key=True),
    Column("type", ActivityEventTypeType, primary_key=True),
    Column(
        "withdrawn_at",
        DateTime,
        nullable=False,
        server_default=text("timezone('utc', now())"),
    ),
)

# El orden del feed: por publicacion y con el id de desempate, como el cursor.
# Fuera de la tabla porque las columnas en DESC se declaran sobre la columna
Index(
    "ix_activity_events_user_published",
    activity_events_table.c.user_id,
    activity_events_table.c.published_at.desc(),
    activity_events_table.c.id.desc(),
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
                "_published_at": activity_events_table.c.published_at,
                "_visible_to_friends": activity_events_table.c.visible_to_friends,
                "_payload": activity_events_table.c.payload,
                "_source_match_id": activity_events_table.c.source_match_id,
            },
        )
