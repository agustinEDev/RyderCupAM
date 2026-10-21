"""
Tests del contador de novedades del feed (el numero del boton de Actividad).

Cuenta todo lo nuevo que el jugador veria en su feed, tambien lo suyo
(decision de producto), y se queda en 10: el cliente pinta «9+», asi que
contar mas seria trabajo tirado.
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
from src.modules.social.domain.value_objects.activity_audience import (
    AUDIENCE_BY_TYPE,
    ActivityAudience,
)
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

VISITA = datetime(2026, 8, 10, 12, 0)
DESPUES = VISITA + timedelta(hours=1)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _create_user(
    user_uow, visto: datetime | None = VISITA, share_activity: bool = True
) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"cnt_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if visto is not None:
        user.mark_feed_as_seen(visto)
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amigos(social_uow, a: User, b: User) -> None:
    friendship = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)


async def _publica(
    social_uow,
    user: User,
    cuantos: int = 1,
    publicado: datetime = DESPUES,
    tipo: ActivityEventType = ActivityEventType.BIRDIE,
    visible_to_friends: bool = True,
) -> None:
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=user.id,
                    type=tipo,
                    occurred_at=VISITA - timedelta(days=1),
                    source_match_id=f"m-{uuid4().hex[:8]}",
                    published_at=publicado + timedelta(seconds=i),
                    visible_to_friends=visible_to_friends,
                )
                for i in range(cuantos)
            ]
        )


async def _cuenta(social_uow, user_uow, user: User) -> int:
    resultado = await GetFeedUnseenCountUseCase(social_uow, user_uow).execute(str(user.id.value))
    return resultado.unseen_count


async def _feed(social_uow, user_uow, user: User):
    return await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(user.id.value))


async def test_c11_sin_visita_previa_cuenta_todo_lo_visible(social_uow, user_uow):
    """
    C11. Given un jugador que nunca abrio Actividad, con 2 logros de un amigo
    y 1 suyo / When se pide el contador / Then 3: todo es nuevo para el.
    """
    yo = await _create_user(user_uow, visto=None)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    await _publica(social_uow, amigo, cuantos=2)
    await _publica(social_uow, yo)

    assert await _cuenta(social_uow, user_uow, yo) == 3


async def test_c12_doce_novedades_se_quedan_en_diez(social_uow, user_uow):
    """C12. Given 12 novedades / When se cuentan / Then 10: el boton pinta «9+»."""
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    await _publica(social_uow, amigo, cuantos=12)

    assert await _cuenta(social_uow, user_uow, yo) == 10


async def test_c12_nueve_se_cuentan_enteras(social_uow, user_uow):
    """Given 9 novedades / When se cuentan / Then 9: el tope no recorta lo que cabe."""
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    await _publica(social_uow, amigo, cuantos=9)

    assert await _cuenta(social_uow, user_uow, yo) == 9


async def test_c13_cuenta_lo_mio_y_lo_de_mis_amigos(social_uow, user_uow):
    """
    C13. Given 2 logros mios y 3 de un amigo publicados tras mi visita, y uno
    viejo / When se cuentan / Then 5: lo propio tambien es novedad.
    """
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    await _publica(social_uow, yo, cuantos=2)
    await _publica(social_uow, amigo, cuantos=3)
    await _publica(social_uow, amigo, publicado=VISITA - timedelta(minutes=1))

    assert await _cuenta(social_uow, user_uow, yo) == 5


async def test_c14_no_cuenta_extranios_ni_amigos_callados(social_uow, user_uow):
    """
    C14. Given un no amigo y un amigo con la publicacion apagada, con logros
    nuevos / When se cuentan / Then 0.
    """
    yo = await _create_user(user_uow)
    extranio = await _create_user(user_uow)
    callado = await _create_user(user_uow, share_activity=False)
    await _amigos(social_uow, yo, callado)
    await _publica(social_uow, extranio, cuantos=2)
    await _publica(social_uow, callado, cuantos=2)

    assert await _cuenta(social_uow, user_uow, yo) == 0


async def test_c14_no_cuenta_lo_que_el_amigo_publico_oculto(social_uow, user_uow):
    """Given un logro de un amigo publicado oculto / When se cuenta / Then no suma."""
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    await _publica(social_uow, amigo, visible_to_friends=False)

    assert await _cuenta(social_uow, user_uow, yo) == 0


async def test_cuenta_segun_el_publico_de_cada_tipo(social_uow, user_uow, monkeypatch):
    """
    Given un tipo SELF y otro FRIENDS / When se cuentan mis novedades / Then
    suman mi SELF y el FRIENDS de mi amigo, no mi FRIENDS ni su SELF.
    """
    monkeypatch.setitem(AUDIENCE_BY_TYPE, ActivityEventType.BIRDIE, ActivityAudience.SELF)
    monkeypatch.setitem(
        AUDIENCE_BY_TYPE, ActivityEventType.EAGLE_OR_BETTER, ActivityAudience.FRIENDS
    )
    yo = await _create_user(user_uow)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    await _publica(social_uow, yo, tipo=ActivityEventType.BIRDIE)
    await _publica(social_uow, yo, tipo=ActivityEventType.EAGLE_OR_BETTER)
    await _publica(social_uow, amigo, tipo=ActivityEventType.BIRDIE)
    await _publica(social_uow, amigo, tipo=ActivityEventType.EAGLE_OR_BETTER)

    assert await _cuenta(social_uow, user_uow, yo) == 2


@pytest.mark.parametrize(("mios", "suyos", "visto"), [(1, 2, VISITA), (4, 8, None), (0, 0, None)])
async def test_c16_coincide_con_el_del_feed(social_uow, user_uow, mios, suyos, visto):
    """
    C16. Given distintas mezclas de novedades / When se piden el contador y el
    feed / Then dicen lo mismo: el boton y la pantalla no pueden discrepar.
    """
    yo = await _create_user(user_uow, visto=visto)
    amigo = await _create_user(user_uow)
    await _amigos(social_uow, yo, amigo)
    if mios:
        await _publica(social_uow, yo, cuantos=mios)
    if suyos:
        await _publica(social_uow, amigo, cuantos=suyos)

    contador = await _cuenta(social_uow, user_uow, yo)
    feed = await _feed(social_uow, user_uow, yo)

    assert feed.unseen_count == contador == min(mios + suyos, 10)
