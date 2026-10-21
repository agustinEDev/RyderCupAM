"""Tests de dar el feed por visto (BE #176)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.mark_feed_as_seen_use_case import (
    MarkFeedAsSeenUseCase,
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
    antes = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=5)

    visto_en = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    assert visto_en > antes


async def test_b8_se_guarda_en_utc_sin_zona(user_uow):
    """
    B8. Given un jugador / When marca el feed / Then la fecha es la de ahora en
    UTC y sin zona: se compara con el `published_at` de los eventos, que se
    escribe asi. Con la hora local quedaria desplazada lo que separe al
    servidor de UTC.
    """
    user = await _create_user(user_uow)
    antes = datetime.now(UTC).replace(tzinfo=None)

    visto_en = await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    despues = datetime.now(UTC).replace(tzinfo=None)
    assert visto_en.tzinfo is None
    assert antes <= visto_en <= despues


async def test_b9_la_marca_nunca_va_hacia_atras(user_uow):
    """
    B9. Given un feed marcado a las 12:00 / When llega otra marca con un reloj
    que va por detras (otro servidor, un ajuste de hora) / Then se queda la de
    las 12:00: retroceder resucitaria como novedad lo ya visto.
    """
    user = await _create_user(user_uow)
    mediodia = datetime(2026, 8, 10, 12, 0)
    await MarkFeedAsSeenUseCase(user_uow, reloj=lambda: mediodia).execute(str(user.id.value))

    visto_en = await MarkFeedAsSeenUseCase(
        user_uow, reloj=lambda: mediodia - timedelta(minutes=5)
    ).execute(str(user.id.value))

    async with user_uow:
        guardado = await user_uow.users.find_by_id(user.id)
    assert guardado.feed_last_seen_at == mediodia
    assert visto_en == mediodia


async def test_b9_una_marca_posterior_si_avanza(user_uow):
    """Given un feed marcado / When se marca mas tarde / Then la fecha avanza."""
    user = await _create_user(user_uow)
    mediodia = datetime(2026, 8, 10, 12, 0)
    await MarkFeedAsSeenUseCase(user_uow, reloj=lambda: mediodia).execute(str(user.id.value))

    await MarkFeedAsSeenUseCase(user_uow, reloj=lambda: mediodia + timedelta(seconds=1)).execute(
        str(user.id.value)
    )

    async with user_uow:
        guardado = await user_uow.users.find_by_id(user.id)
    assert guardado.feed_last_seen_at == mediodia + timedelta(seconds=1)


async def test_b10_tras_marcarlo_el_aviso_queda_a_cero(user_uow):
    """
    B10. Given un logro mio recien publicado (hora UTC) / When marco el feed
    como visto con el reloj de verdad / Then el aviso queda a cero.
    """
    user = await _create_user(user_uow)
    social_uow = InMemorySocialUnitOfWork()
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=user.id,
                    type=ActivityEventType.BIRDIE,
                    occurred_at=datetime(2026, 8, 1),
                    source_match_id="match-1",
                )
            ]
        )

    await MarkFeedAsSeenUseCase(user_uow).execute(str(user.id.value))

    feed = await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(user.id.value))
    assert len(feed.events) == 1
    assert feed.unseen_count == 0


async def test_un_jugador_que_no_existe_falla(user_uow):
    """Given un id inventado / When se marca / Then falla."""
    with pytest.raises(UserNotFoundError):
        await MarkFeedAsSeenUseCase(user_uow).execute(str(uuid4()))
