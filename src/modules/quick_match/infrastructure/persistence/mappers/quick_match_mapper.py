"""
SQLAlchemy Mapper for QuickMatch aggregate (QuickMatch module).

Tablas:
- quick_matches (agregado raiz; participantes y scorer_ids como JSONB embebido)
- quick_match_hole_scores (scores por hoyo, modelo simple sin validacion dual)
"""

import uuid
from typing import Any

import sqlalchemy.types
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import CHAR

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
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


class ParticipantIdType(sqlalchemy.types.TypeDecorator[ParticipantId]):
    """TypeDecorator para ParticipantId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: ParticipantId | None, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value.value

    def process_result_value(
        self, value: uuid.UUID | None, dialect: Any
    ) -> ParticipantId | None:
        if value is None:
            return None
        return ParticipantId(value)


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


class PlayModeType(sqlalchemy.types.TypeDecorator[PlayMode]):
    """
    TypeDecorator local para PlayMode (VO compartido con `competition`).

    Como MatchFormatType: se comparte el Value Object, no el decorator, para no
    acoplar la persistencia de los dos modulos.
    """

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: PlayMode | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: str | None, dialect: Any) -> PlayMode | None:
        if value is None:
            return None
        return PlayMode(value)


class ScoringFormatType(sqlalchemy.types.TypeDecorator[ScoringFormat]):
    """TypeDecorator para ScoringFormat (VO local a quick_match, formato de partido libre)."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: ScoringFormat | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: str | None, dialect: Any) -> ScoringFormat | None:
        if value is None:
            return None
        return ScoringFormat(value)


class QuickMatchParticipantsJsonType(sqlalchemy.types.TypeDecorator[list]):
    """
    TypeDecorator para serializar list[QuickMatchParticipant] a/desde JSONB.

    Cada QuickMatchParticipant se serializa como:
    {
        "participant_id": "uuid-string",
        "user_id": "uuid-string" | null,       # null para invitados
        "first_name": "..." | null,             # solo invitados
        "last_name": "..." | null,              # solo invitados
        "handicap": number | null,              # solo invitados (opcional)
        "custom_handicap": number | null,       # solo registrados (override, opcional)
        "team": "A" | "B" | null,
        "tee_color": "YELLOW" | ... | null,
        "tee_gender": "MALE" | "FEMALE" | null
    }
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: list | None, dialect: Any) -> list | None:
        if value is None:
            return None
        return [
            {
                "participant_id": str(p.participant_id.value),
                "user_id": str(p.user_id.value) if p.user_id else None,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "handicap": p.handicap,
                "custom_handicap": p.custom_handicap,
                "team": p.team,
                "tee_color": p.tee_color.value if p.tee_color else None,
                "tee_gender": p.tee_gender.value if p.tee_gender else None,
            }
            for p in value
        ]

    def process_result_value(self, value: list | None, dialect: Any) -> list | None:
        if value is None:
            return None
        participants = []
        for p in value:
            participants.append(
                QuickMatchParticipant(
                    participant_id=ParticipantId(p["participant_id"]),
                    user_id=UserId(uuid.UUID(p["user_id"])) if p.get("user_id") else None,
                    first_name=p.get("first_name"),
                    last_name=p.get("last_name"),
                    handicap=p.get("handicap"),
                    custom_handicap=p.get("custom_handicap"),
                    team=p.get("team"),
                    tee_color=(
                        TeeColor(p["tee_color"]) if p.get("tee_color") else None
                    ),
                    tee_gender=Gender(p["tee_gender"]) if p.get("tee_gender") else None,
                )
            )
        return participants


class ScorerIdsJsonType(sqlalchemy.types.TypeDecorator[list]):
    """
    TypeDecorator para serializar list[ParticipantId] a/desde JSONB.

    Generico: se reutiliza tanto para `scorer_ids` como para
    `hidden_by_participant_ids` (misma forma, listas de ParticipantId).
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: list | None, dialect: Any) -> list | None:
        if value is None:
            return None
        return [str(pid.value) for pid in value]

    def process_result_value(self, value: list | None, dialect: Any) -> list | None:
        if value is None:
            return []
        return [ParticipantId(v) for v in value]


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
    Column("match_format", MatchFormatType, nullable=True),
    Column("scoring_format", ScoringFormatType, nullable=True),
    Column("status", QuickMatchStatusType, nullable=False),
    Column("name", String(100), nullable=True),
    Column("allowance_percentage", Integer, nullable=True),
    Column("play_mode", PlayModeType, nullable=False, default=PlayMode.HANDICAP),
    Column("participants", QuickMatchParticipantsJsonType, nullable=False),
    Column("scorer_ids", ScorerIdsJsonType, nullable=False, default=list),
    Column("hidden_by_participant_ids", ScorerIdsJsonType, nullable=False, default=list),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    CheckConstraint(
        "(match_format IS NULL) <> (scoring_format IS NULL)",
        name="ck_quick_matches_exactly_one_format",
    ),
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
    # participant_id NO tiene FK a `users`: puede ser un invitado sin cuenta.
    Column("participant_id", ParticipantIdType, nullable=False),
    Column("score", Integer, nullable=False),
    Column("recorded_by_participant_id", ParticipantIdType, nullable=False),
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
                "_scoring_format": quick_matches_table.c.scoring_format,
                "_status": quick_matches_table.c.status,
                "_name": quick_matches_table.c.name,
                "_allowance_percentage": quick_matches_table.c.allowance_percentage,
                "_play_mode": quick_matches_table.c.play_mode,
                "_participants": quick_matches_table.c.participants,
                "_scorer_ids": quick_matches_table.c.scorer_ids,
                "_hidden_by_participant_ids": quick_matches_table.c.hidden_by_participant_ids,
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
                "_participant_id": quick_match_hole_scores_table.c.participant_id,
                "_score": quick_match_hole_scores_table.c.score,
                "_recorded_by_participant_id": (
                    quick_match_hole_scores_table.c.recorded_by_participant_id
                ),
                "_created_at": quick_match_hole_scores_table.c.created_at,
                "_updated_at": quick_match_hole_scores_table.c.updated_at,
            },
        )
