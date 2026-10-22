"""
Logros exclusivos por fecha real (22 oct 2026) contra Postgres: la lectura de
lo publicado por jugador, el candado de jugador y la regla de quedarse con el
mas antiguo sobre filas de verdad (payload JSONB y fechas guardadas).
"""

from datetime import datetime

import pytest

from src.modules.social.application.exclusive_achievements import (
    keep_only_the_oldest,
    lock_players,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration

T = ActivityEventType
CAMPO = "campo-1"


async def _usuario(db_session, email: str) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=email,
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _logro(user, tipo, origen, jugado: datetime | None, **extra) -> ActivityEvent:
    payload = {"golf_course_id": CAMPO, **extra}
    if jugado is not None:
        payload["played_at"] = jugado.isoformat() + "Z"
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=jugado or datetime(2026, 6, 1, 12),
        source_match_id=origen,
        payload=payload,
    )


async def test_finds_what_those_players_published_of_those_types(db_session):
    ana = await _usuario(db_session, "exclu-1@example.com")
    bea = await _usuario(db_session, "exclu-2@example.com")
    repo = SQLAlchemyActivityEventRepository(db_session)
    await repo.add_many(
        [
            _logro(ana, T.NEW_COURSE, "r-1", datetime(2026, 6, 1, 7)),
            _logro(ana, T.BIRDIE, "r-1", None),
            _logro(bea, T.NEW_COURSE, "r-2", datetime(2026, 6, 1, 7)),
        ]
    )
    await db_session.commit()

    encontrados = await repo.find_for_users([ana.id], [T.NEW_COURSE, T.FIRST_TOURNAMENT])

    assert [(e.user_id, e.type, e.source_match_id) for e in encontrados] == [
        (ana.id, T.NEW_COURSE, "r-1")
    ]
    assert await repo.find_for_users([], [T.NEW_COURSE]) == []
    assert await repo.find_for_users([ana.id], []) == []


async def test_the_oldest_stays_and_the_later_ones_are_withdrawn(db_session):
    ana = await _usuario(db_session, "exclu-3@example.com")
    repo = SQLAlchemyActivityEventRepository(db_session)
    await repo.add_many(
        [
            _logro(ana, T.NEW_COURSE, "tarde", datetime(2026, 6, 1, 10)),
            # De antes de llevar `played_at`: cuenta su `occurred_at`
            _logro(ana, T.NEW_COURSE, "vieja", None),
        ]
    )
    await db_session.commit()

    await lock_players(repo, [ana.id])
    nuevo = _logro(ana, T.NEW_COURSE, "manana", datetime(2026, 6, 1, 4))
    quedan = await keep_only_the_oldest(repo, [nuevo], is_own=lambda e: False)
    await repo.add_many(quedan)
    await db_session.commit()

    publicados = await repo.find_for_users([ana.id], [T.NEW_COURSE])
    assert [e.source_match_id for e in publicados] == ["manana"]


async def test_a_later_one_is_not_published_over_an_older_one(db_session):
    ana = await _usuario(db_session, "exclu-4@example.com")
    repo = SQLAlchemyActivityEventRepository(db_session)
    await repo.add_many([_logro(ana, T.NEW_COURSE, "manana", datetime(2026, 6, 1, 4))])
    await db_session.commit()

    await lock_players(repo, [ana.id])
    nuevo = _logro(ana, T.NEW_COURSE, "tarde", datetime(2026, 6, 1, 10))
    assert await keep_only_the_oldest(repo, [nuevo], is_own=lambda e: False) == []
    await db_session.commit()

    publicados = await repo.find_for_users([ana.id], [T.NEW_COURSE])
    assert [e.source_match_id for e in publicados] == ["manana"]
