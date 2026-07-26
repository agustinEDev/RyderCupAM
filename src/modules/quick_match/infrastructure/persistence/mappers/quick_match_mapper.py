"""
SQLAlchemy Mapper for QuickMatch aggregate (QuickMatch module).

Tablas:
- quick_matches (agregado raiz; participantes como JSONB embebido)
- quick_match_hole_scores (scores por hoyo, modelo simple sin validacion dual)
"""

import uuid
from typing import Any

import sqlalchemy.types
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import CHAR

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata

# ============================================================================
# TypeDecorators for Value Objects (MUST be before tables)
# ============================================================================


class QuickMatchIdType(sqlalchemy.types.TypeDecorator[QuickMatchId]):
    """TypeDecorator para QuickMatchId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: QuickMatchId | None, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: uuid.UUID | None, dialect: Any) -> QuickMatchId | None:
        if value is None:
            return None
        return QuickMatchId(value)


class QuickMatchHoleScoreIdType(sqlalchemy.types.TypeDecorator[QuickMatchHoleScoreId]):
    """TypeDecorator para QuickMatchHoleScoreId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(
        self, value: QuickMatchHoleScoreId | None, dialect: Any
    ) -> uuid.UUID | None:
        if value is None:
            return None
        return value.value

    def process_result_value(
        self, value: uuid.UUID | None, dialect: Any
    ) -> QuickMatchHoleScoreId | None:
        if value is None:
            return None
        return QuickMatchHoleScoreId(value)


class QuickMatchUserIdType(sqlalchemy.types.TypeDecorator[UserId]):
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


class QuickMatchGolfCourseIdType(sqlalchemy.types.TypeDecorator[GolfCourseId]):
    """TypeDecorator local para GolfCourseId (compatible con golf_courses.id UUID)."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: GolfCourseId | None, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: uuid.UUID | None, dialect: Any) -> GolfCourseId | None:
        if value is None:
            return None
        return GolfCourseId(value)


class QuickMatchStatusType(sqlalchemy.types.TypeDecorator[QuickMatchStatus]):
    """TypeDecorator para QuickMatchStatus Value Object."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: QuickMatchStatus | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(
        self, value: str | None, dialect: Any
    ) -> QuickMatchStatus | None:
        if value is None:
            return None
        return QuickMatchStatus(value)


class MatchFormatType(sqlalchemy.types.TypeDecorator[MatchFormat]):
    """
    TypeDecorator local para MatchFormat (VO compartido con `competition`).

    Se define localmente (en vez de importar el decorator de `competition`)
    para mantener el modulo `quick_match` desacoplado de la infraestructura
    de persistencia de `competition`.
    """

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: MatchFormat | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: str | None, dialect: Any) -> MatchFormat | None:
        if value is None:
            return None
        return MatchFormat(value)


class QuickMatchParticipantsJsonType(sqlalchemy.types.TypeDecorator[list]):
    """
    TypeDecorator para serializar list[QuickMatchParticipant] a/desde JSONB.

    Cada QuickMatchParticipant se serializa como:
    {"user_id": "uuid-string", "team": "A" | "B" | null}
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: list | None, dialect: Any) -> list | None:
        if value is None:
            return None
        return [{"user_id": str(p.user_id.value), "team": p.team} for p in value]

    def process_result_value(self, value: list | None, dialect: Any) -> list | None:
        if value is None:
            return None
        return [
            QuickMatchParticipant(user_id=UserId(uuid.UUID(p["user_id"])), team=p["team"])
            for p in value
        ]


# ============================================================================
# TABLA QUICK_MATCHES
# ============================================================================

quick_matches_table = Table(
    "quick_matches",
    metadata,
    Column("id", QuickMatchIdType, primary_key=True),
    Column(
        "creator_id",
        QuickMatchUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "golf_course_id",
        QuickMatchGolfCourseIdType,
        ForeignKey("golf_courses.id"),
        nullable=False,
    ),
    Column("match_format", MatchFormatType, nullable=False),
    Column("status", QuickMatchStatusType, nullable=False),
    Column("participants", QuickMatchParticipantsJsonType, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# ============================================================================
# TABLA QUICK_MATCH_HOLE_SCORES
# ============================================================================

quick_match_hole_scores_table = Table(
    "quick_match_hole_scores",
    metadata,
    Column("id", QuickMatchHoleScoreIdType, primary_key=True),
    Column(
        "quick_match_id",
        QuickMatchIdType,
        ForeignKey("quick_matches.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("hole_number", Integer, nullable=False),
    Column(
        "player_user_id",
        QuickMatchUserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("score", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


def start_quick_match_mappers() -> None:
    """
    Inicia el mapeo entre entidades del modulo QuickMatch y tablas de BD.

    Es idempotente: puede llamarse multiples veces sin efectos adversos.
    """
    if not any(mapper.class_ is QuickMatch for mapper in mapper_registry.mappers):
        mapper_registry.map_imperatively(
            QuickMatch,
            quick_matches_table,
            properties={
                "_id": quick_matches_table.c.id,
                "_creator_id": quick_matches_table.c.creator_id,
                "_golf_course_id": quick_matches_table.c.golf_course_id,
                "_match_format": quick_matches_table.c.match_format,
                "_status": quick_matches_table.c.status,
                "_participants": quick_matches_table.c.participants,
                "_created_at": quick_matches_table.c.created_at,
                "_updated_at": quick_matches_table.c.updated_at,
            },
        )

    if not any(mapper.class_ is QuickMatchHoleScore for mapper in mapper_registry.mappers):
        mapper_registry.map_imperatively(
            QuickMatchHoleScore,
            quick_match_hole_scores_table,
            properties={
                "_id": quick_match_hole_scores_table.c.id,
                "_quick_match_id": quick_match_hole_scores_table.c.quick_match_id,
                "_hole_number": quick_match_hole_scores_table.c.hole_number,
                "_player_user_id": quick_match_hole_scores_table.c.player_user_id,
                "_score": quick_match_hole_scores_table.c.score,
                "_created_at": quick_match_hole_scores_table.c.created_at,
                "_updated_at": quick_match_hole_scores_table.c.updated_at,
            },
        )
