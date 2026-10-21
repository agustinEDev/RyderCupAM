"""
E23. El feed carga a sus autores de una vez, no uno por uno.

Antes se pedia cada amigo (para saber si publica) y cada autor (para pintarlo)
con su propia consulta: el coste crecia con los amigos y con la pagina.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.use_cases.get_feed_unseen_count_use_case import (
    GetFeedUnseenCountUseCase,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

CUANDO = datetime(2026, 8, 10, 12, 0)


class _Contador:
    """Envuelve el repositorio de usuarios y cuenta cada lectura."""

    def __init__(self, repo):
        self._repo = repo
        self.por_id = 0
        self.por_ids = 0

    async def find_by_id(self, user_id):
        self.por_id += 1
        return await self._repo.find_by_id(user_id)

    async def find_by_ids(self, user_ids):
        self.por_ids += 1
        return await self._repo.find_by_ids(user_ids)

    def __getattr__(self, name):
        return getattr(self._repo, name)


async def _escenario(amigos: int, logros_por_amigo: int):
    social_uow = InMemorySocialUnitOfWork()
    user_uow = InMemoryUserUnitOfWork()

    async def _user() -> User:
        user = User.create(
            first_name="Ana",
            last_name="Garcia",
            email_str=f"n1_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    yo = await _user()
    for _ in range(amigos):
        amigo = await _user()
        friendship = Friendship.create(
            id=FriendshipId(uuid4()), requester_id=yo.id, addressee_id=amigo.id
        )
        friendship.accept()
        async with social_uow:
            await social_uow.friendships.add(friendship)
            await social_uow.activity_events.add_many(
                [
                    ActivityEvent.create(
                        user_id=amigo.id,
                        type=ActivityEventType.BIRDIE,
                        occurred_at=CUANDO,
                        source_match_id=f"m-{uuid4().hex[:8]}",
                        published_at=CUANDO - timedelta(minutes=i),
                    )
                    for i in range(logros_por_amigo)
                ]
            )

    contador = _Contador(user_uow.users)
    user_uow._users = contador
    return social_uow, user_uow, yo, contador


@pytest.mark.parametrize(("amigos", "logros"), [(1, 1), (8, 3)])
async def test_e23_el_feed_lee_los_usuarios_en_lecturas_fijas(amigos, logros):
    """
    E23. Given 1 amigo con 1 logro, o 8 con 3 cada uno / When pido el feed /
    Then los usuarios se leen en dos lecturas por lote (amigos y autores) y
    ninguna de uno en uno.
    """
    social_uow, user_uow, yo, contador = await _escenario(amigos, logros)

    feed = await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(yo.id.value), limit=50)

    assert len(feed.events) == amigos * logros
    assert len(feed.authors) == amigos
    assert contador.por_id == 0
    assert contador.por_ids == 2


async def test_e23_el_contador_lee_los_usuarios_de_una_vez():
    """Given 8 amigos / When pido el contador / Then una sola lectura de usuarios."""
    social_uow, user_uow, yo, contador = await _escenario(8, 1)

    await GetFeedUnseenCountUseCase(social_uow, user_uow).execute(str(yo.id.value))

    assert contador.por_id == 0
    assert contador.por_ids == 1
