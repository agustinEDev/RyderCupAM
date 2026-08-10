"""
Tests del interruptor de publicacion de logros (BE #175).

Lo que se comprueba aqui, sobre todo: **apagarlo retira lo ya publicado**. Quien
lo apaga quiere que lo suyo deje de verse, no que se congele donde estaba.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.social.application.use_cases.set_activity_sharing_use_case import (
    SetActivitySharingUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


async def _create_user(user_uow) -> User:
    user = User.create(
        first_name="Test",
        last_name="User",
        email_str=f"switch_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _publica(social_uow, user, match_id: str) -> None:
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=user.id,
                    type=ActivityEventType.BIRDIE,
                    occurred_at=datetime(2026, 8, 10),
                    source_match_id=match_id,
                )
            ]
        )


async def _feed_de(social_uow, user):
    async with social_uow:
        return await social_uow.activity_events.find_for_users([user.id], limit=50)


async def test_apagarlo_retira_lo_ya_publicado(user_uow, social_uow):
    """
    Given un jugador con logros publicados / When apaga la publicacion / Then
    su historial desaparece del feed, no solo deja de crecer.
    """
    user = await _create_user(user_uow)
    await _publica(social_uow, user, "match-1")
    await _publica(social_uow, user, "match-2")

    retirados = await SetActivitySharingUseCase(user_uow, social_uow).execute(
        str(user.id.value), enabled=False
    )

    assert retirados == 2
    assert await _feed_de(social_uow, user) == []


async def test_apagarlo_no_toca_lo_de_los_demas(user_uow, social_uow):
    """Given dos jugadores publicando / When uno lo apaga / Then el otro sigue."""
    ana = await _create_user(user_uow)
    luis = await _create_user(user_uow)
    await _publica(social_uow, ana, "match-1")
    await _publica(social_uow, luis, "match-2")

    await SetActivitySharingUseCase(user_uow, social_uow).execute(
        str(ana.id.value), enabled=False
    )

    assert await _feed_de(social_uow, ana) == []
    assert len(await _feed_de(social_uow, luis)) == 1


async def test_apagarlo_deja_el_interruptor_guardado(user_uow, social_uow):
    """Given un jugador / When lo apaga / Then su perfil lo recuerda."""
    user = await _create_user(user_uow)

    await SetActivitySharingUseCase(user_uow, social_uow).execute(
        str(user.id.value), enabled=False
    )

    async with user_uow:
        guardado = await user_uow.users.find_by_id(user.id)
    assert guardado.share_activity is False


async def test_encenderlo_no_borra_ni_recupera_nada(user_uow, social_uow):
    """
    Given un jugador que lo vuelve a encender / When lo enciende / Then no se
    borra nada, y lo retirado antes no vuelve: se llena con lo que juegue.
    """
    user = await _create_user(user_uow)
    await _publica(social_uow, user, "match-1")

    retirados = await SetActivitySharingUseCase(user_uow, social_uow).execute(
        str(user.id.value), enabled=True
    )

    assert retirados == 0
    assert len(await _feed_de(social_uow, user)) == 1
    async with user_uow:
        guardado = await user_uow.users.find_by_id(user.id)
    assert guardado.share_activity is True


async def test_un_jugador_que_no_existe_falla(user_uow, social_uow):
    """Given un id que no existe / When se cambia el interruptor / Then falla."""
    with pytest.raises(UserNotFoundError):
        await SetActivitySharingUseCase(user_uow, social_uow).execute(
            str(uuid4()), enabled=False
        )
