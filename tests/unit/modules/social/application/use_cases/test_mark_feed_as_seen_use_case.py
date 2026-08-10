"""Tests de dar el feed por visto (BE #176)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.application.use_cases.mark_feed_as_seen_use_case import (
    MarkFeedAsSeenUseCase,
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


async def _create_user(user_uow) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"seen_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def test_guarda_cuando_se_miro_el_feed(user_uow):
    """Given un jugador que nunca lo abrio / When lo marca / Then queda la fecha."""
    user = await _create_user(user_uow)
    assert user.feed_last_seen_at is None

    visto_en = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    async with user_uow:
        guardado = await user_uow.users.find_by_id(user.id)
    assert guardado.feed_last_seen_at == visto_en


async def test_marcarlo_dos_veces_adelanta_la_fecha(user_uow):
    """Given un feed ya marcado / When se marca otra vez / Then la fecha avanza."""
    user = await _create_user(user_uow)
    primera = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    segunda = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    assert segunda >= primera


async def test_guarda_el_momento_de_la_llamada_y_no_una_fecha_del_pasado(user_uow):
    """
    Given un jugador / When marca el feed / Then la fecha es de ahora.

    Importa que sea el momento de la llamada y no la del ultimo evento leido:
    lo que se publique mientras lee debe volver a contar como novedad.
    """
    user = await _create_user(user_uow)
    antes = datetime.now() - timedelta(seconds=5)

    visto_en = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    assert visto_en > antes


async def test_la_fecha_es_comparable_con_la_de_los_eventos(user_uow):
    """
    Given un logro publicado ahora / When se marca el feed como visto / Then la
    marca queda por delante del logro, asi que deja de contar como novedad.

    Fija la regla horaria: esta fecha se compara con el `occurred_at` de los
    eventos, que el dominio escribe con `datetime.now()`. Si se guardara en UTC,
    quedaria desplazada y los logros de las ultimas horas contarian como no
    vistos para siempre.
    """
    user = await _create_user(user_uow)
    ocurrio_ahora = datetime.now()

    visto_en = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    assert visto_en >= ocurrio_ahora


async def test_un_jugador_que_no_existe_falla(user_uow):
    """Given un id inventado / When se marca / Then falla."""
    with pytest.raises(UserNotFoundError):
        await MarkFeedAsSeenUseCase(user_uow).execute(str(uuid4()))
