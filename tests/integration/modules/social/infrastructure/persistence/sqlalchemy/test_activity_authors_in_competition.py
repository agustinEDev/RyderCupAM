"""
Los autores con algún evento de una competición, en PostgreSQL (tabla del 27 oct 2026).

Es la llave de una privada: el `competition_id` vive dentro del JSONB, como
texto, y la consulta tiene que respetar el trozo (jugadores, tipos y lo oculto).
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
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
CUANDO = datetime(2026, 10, 20, 12, 0)


async def _user(db_session) -> User:
    user = User.create(
        first_name="Llave",
        last_name="Privada",
        email_str=f"llave-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _evento(user: User, torneo: str, tipo=T.BIRDIE, *, visible=True) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=f"grupo-{uuid4().hex[:6]}",
        published_at=CUANDO,
        payload={"competition_id": torneo, "from_tournament": True},
        visible_to_friends=visible,
    )


def _trozo(*users: User, tipos=(T.BIRDIE, T.TOURNAMENT_FINAL_STANDING)) -> ActivitySlice:
    return ActivitySlice(
        user_ids=tuple(u.id for u in users), types=frozenset(tipos), only_visible_to_friends=True
    )


async def test_only_the_authors_of_that_competition_once_each(db_session):
    ana, beto, carla = await _user(db_session), await _user(db_session), await _user(db_session)
    torneo, otro = str(uuid4()), str(uuid4())
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(ana, torneo),
            _evento(ana, torneo, T.TOURNAMENT_FINAL_STANDING),
            _evento(beto, otro),
            _evento(carla, torneo),
        ]
    )
    await db_session.commit()

    assert await repository.authors_in_competition(_trozo(ana, beto), torneo) == {ana.id}


async def test_types_and_hidden_events_out_of_the_slice_do_not_count(db_session):
    ana, beto = await _user(db_session), await _user(db_session)
    torneo = str(uuid4())
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(ana, torneo, T.ENROLLED_IN_TOURNAMENT),
            _evento(beto, torneo, visible=False),
        ]
    )
    await db_session.commit()

    assert await repository.authors_in_competition(_trozo(ana, beto), torneo) == set()


async def test_an_empty_slice_does_not_query(db_session):
    repository = SQLAlchemyActivityEventRepository(db_session)

    assert await repository.authors_in_competition(_trozo(), str(uuid4())) == set()
