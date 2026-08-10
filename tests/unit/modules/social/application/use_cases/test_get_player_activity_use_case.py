"""
Tests de la actividad de un jugador (BE #176).

Mismo guard que el perfil, con una diferencia que importa: el interruptor de
publicacion apagado **no es un error**. El perfil sigue siendo visible; lo que
no hay es actividad que enseñar.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
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


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _create_user(user_uow, share_activity: bool = True) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"act_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _hacer_amigos(social_uow, a: User, b: User) -> None:
    friendship = Friendship.create(
        id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id
    )
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)


async def _publica(social_uow, user: User, match_id: str, cuando: datetime = CUANDO):
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=user.id,
                    type=ActivityEventType.BIRDIE,
                    occurred_at=cuando,
                    source_match_id=match_id,
                )
            ]
        )


def _use_case(social_uow, user_uow):
    return GetPlayerActivityUseCase(social_uow, user_uow)


async def test_un_amigo_ve_la_actividad(social_uow, user_uow):
    """Given un amigo con logros / When pido su actividad / Then los veo."""
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _hacer_amigos(social_uow, yo, amigo)
    await _publica(social_uow, amigo, "match-1")

    resultado = await _use_case(social_uow, user_uow).execute(
        str(yo.id.value), str(amigo.id.value)
    )

    assert len(resultado.events) == 1
    assert resultado.events[0].source_match_id == "match-1"


async def test_un_desconocido_no_ve_la_actividad(social_uow, user_uow):
    """
    Given dos sin amistad / When se pide la actividad / Then se rechaza.

    La actividad es solo para amigos, a diferencia de la ficha del perfil. Y el
    rechazo es explicito, no un "no existe": el jugador si existe y quien
    pregunta ya ha podido ver su ficha.
    """
    yo = await _create_user(user_uow)
    extranio = await _create_user(user_uow)
    await _publica(social_uow, extranio, "match-1")

    with pytest.raises(ActivityNotVisibleError):
        await _use_case(social_uow, user_uow).execute(
            str(yo.id.value), str(extranio.id.value)
        )


async def test_un_jugador_que_no_existe_da_un_error_distinto(social_uow, user_uow):
    """
    Given un id inventado / When se pide su actividad / Then el error dice que
    no existe, no que sea privado: son dos situaciones distintas y el cliente
    reacciona distinto a cada una.
    """
    yo = await _create_user(user_uow)

    with pytest.raises(ProfileNotVisibleError):
        await _use_case(social_uow, user_uow).execute(str(yo.id.value), str(uuid4()))


async def test_el_interruptor_apagado_no_es_un_error(social_uow, user_uow):
    """
    Given un amigo con la publicacion apagada / When pido su actividad / Then
    llega vacia, no un error: su perfil existe y es visible.
    """
    yo = await _create_user(user_uow)
    callado = await _create_user(user_uow, share_activity=False)
    await _hacer_amigos(social_uow, yo, callado)
    await _publica(social_uow, callado, "match-1")

    resultado = await _use_case(social_uow, user_uow).execute(
        str(yo.id.value), str(callado.id.value)
    )

    assert resultado.events == []


async def test_puedo_ver_mi_propia_actividad(social_uow, user_uow):
    """Given un jugador sin amigos / When pide su propia actividad / Then la ve."""
    yo = await _create_user(user_uow)
    await _publica(social_uow, yo, "match-1")

    resultado = await _use_case(social_uow, user_uow).execute(
        str(yo.id.value), str(yo.id.value)
    )

    assert len(resultado.events) == 1


async def test_solo_sale_la_actividad_del_jugador_pedido(social_uow, user_uow):
    """Given dos amigos con logros / When pido la de uno / Then no sale la del otro."""
    yo = await _create_user(user_uow)
    uno = await _create_user(user_uow)
    otro = await _create_user(user_uow)
    await _hacer_amigos(social_uow, yo, uno)
    await _hacer_amigos(social_uow, yo, otro)
    await _publica(social_uow, uno, "de-uno")
    await _publica(social_uow, otro, "de-otro")

    resultado = await _use_case(social_uow, user_uow).execute(
        str(yo.id.value), str(uno.id.value)
    )

    assert [e.source_match_id for e in resultado.events] == ["de-uno"]


async def test_pagina_con_cursor(social_uow, user_uow):
    """Given 5 logros / When paso paginas de 2 / Then salen los 5 sin repetir."""
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _hacer_amigos(social_uow, yo, amigo)
    for i in range(5):
        await _publica(social_uow, amigo, f"match-{i}", CUANDO - timedelta(days=i))
    use_case = _use_case(social_uow, user_uow)

    vistos, cursor = [], None
    while True:
        pagina = await use_case.execute(
            str(yo.id.value), str(amigo.id.value), limit=2, cursor=cursor
        )
        vistos.extend(pagina.events)
        cursor = pagina.next_cursor
        if cursor is None:
            break

    assert len({e.id for e in vistos}) == 5
