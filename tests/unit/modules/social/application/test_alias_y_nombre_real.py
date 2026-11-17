"""
Nombre y alias, los dos, en el perfil, el feed y las amistades (SB-08, 17 nov 2026).

El alias es el apodo con el que te conocen tus amigos, no un dato oculto: la app enseña
el alias delante y el nombre real pequeño debajo. Para eso la API manda los dos.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.social.application.feed_references import autores_de
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.application.use_cases.list_friends_use_case import ListFriendsUseCase
from src.modules.social.application.use_cases.list_pending_requests_use_case import (
    ListPendingRequestsUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.dto.player_stats_dto import PlayerStatsResponseDTO
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio


async def _usuario(user_uow, nombre: str, alias: str | None = None) -> User:
    user = User.create(nombre, "Real", f"{nombre.lower()}-{uuid4().hex[:6]}@t.com", "P@ssw0rd123!")
    if alias:
        user.update_profile(alias=alias)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _solicitud(social_uow, de: User, a: User, aceptada: bool) -> Friendship:
    f = Friendship.create(id=FriendshipId(uuid4()), requester_id=de.id, addressee_id=a.id)
    if aceptada:
        f.accept()
    async with social_uow:
        await social_uow.friendships.add(f)
    return f


async def test_the_profile_carries_the_alias_and_the_real_name():
    social_uow, user_uow = InMemorySocialUnitOfWork(), InMemoryUserUnitOfWork()
    trinx = await _usuario(user_uow, "Agustin", alias="Trinx")
    otro = await _usuario(user_uow, "Otro")
    stats = AsyncMock()
    stats.execute.return_value = PlayerStatsResponseDTO(handicap=None, rounds_played=0)

    perfil = await GetPlayerProfileUseCase(social_uow, user_uow, stats).execute(
        str(otro.id.value), str(trinx.id.value)
    )

    assert (perfil.display_name, perfil.alias) == ("Trinx", "Trinx")
    assert (perfil.first_name, perfil.last_name) == ("Agustin", "Real")


async def test_feed_authors_carry_the_alias():
    social_uow, user_uow = InMemorySocialUnitOfWork(), InMemoryUserUnitOfWork()
    trinx = await _usuario(user_uow, "Agustin", alias="Trinx")
    yo = await _usuario(user_uow, "Yo")
    evento = ActivityEvent.create(
        user_id=trinx.id,
        type=ActivityEventType.QUICK_MATCH_FINISHED,
        occurred_at=datetime(2026, 8, 10, 12, 0),
        source_match_id="p-1",
    )

    autores = await autores_de(social_uow, user_uow, [evento], yo.id)

    autor = autores[str(trinx.id.value)]
    assert (autor.display_name, autor.alias, autor.first_name) == ("Trinx", "Trinx", "Agustin")


async def test_friends_and_requests_carry_real_name_and_alias_of_both_sides():
    social_uow, user_uow = InMemorySocialUnitOfWork(), InMemoryUserUnitOfWork()
    trinx = await _usuario(user_uow, "Agustin", alias="Trinx")
    ana = await _usuario(user_uow, "Ana")
    pepe = await _usuario(user_uow, "Pepe", alias="Pepito")
    await _solicitud(social_uow, trinx, ana, aceptada=True)
    await _solicitud(social_uow, pepe, ana, aceptada=False)

    amigos = await ListFriendsUseCase(social_uow, user_uow).execute(str(ana.id.value))
    pendientes = await ListPendingRequestsUseCase(social_uow, user_uow).execute(str(ana.id.value))

    [amistad] = amigos.friendships
    assert (amistad.requester_name, amistad.requester_alias) == ("Trinx", "Trinx")
    assert amistad.requester_real_name == "Agustin Real"
    assert (amistad.addressee_real_name, amistad.addressee_alias) == ("Ana Real", None)
    [solicitud] = pendientes.friendships
    assert (solicitud.requester_real_name, solicitud.requester_alias) == ("Pepe Real", "Pepito")
