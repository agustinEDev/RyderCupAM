"""Tests de integracion del contador de novedades por tarjeta (E22, BE-2)."""

from datetime import datetime, timedelta
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
CUANDO = datetime(2026, 10, 22, 12, 0)
TODOS = frozenset(ActivityEventType)


async def _user(db_session) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"notice-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _evento(user: User, tipo: ActivityEventType, origen: str) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=origen,
        published_at=CUANDO + timedelta(minutes=1),
        payload={"competition_id": origen},
    )


async def test_e22_el_numero_cuenta_tarjetas(db_session):
    """
    E22. Given tres logros de una vuelta, uno de otra y dos avisos del mismo
    torneo / When se cuenta / Then cuatro tarjetas: los logros de la vuelta son una.
    """
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(user, T.BIRDIE, "vuelta-1"),
            _evento(user, T.EAGLE_OR_BETTER, "vuelta-1"),
            _evento(user, T.NEW_COURSE, "vuelta-1"),
            _evento(user, T.BIRDIE, "vuelta-2"),
            _evento(user, T.ENROLLMENT_APPROVED, "torneo-1"),
            _evento(user, T.ENROLLED_IN_TOURNAMENT, "torneo-1"),
        ]
    )
    await db_session.commit()

    trozo = [ActivitySlice(user_ids=(user.id,), types=TODOS)]

    assert await repository.count_in(trozo, since=CUANDO) == 4
    assert await repository.count_in(trozo, since=CUANDO, cap=3) == 3
    assert await repository.count_in(trozo, since=CUANDO + timedelta(hours=1)) == 0
