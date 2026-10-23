"""
Tests del publico de cada evento en el feed, la actividad y el interruptor.

Cada tipo de evento tiene un publico: SELF (solo su autor), FRIENDS (solo sus
amigos) o BOTH. Los seis logros de hoy son BOTH; los tipos SELF y FRIENDS
llegan despues, asi que aqui se prueba el mecanismo cambiando el mapa del
dominio para el test.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.exceptions import ActivityNotVisibleError
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
)
from src.modules.social.application.use_cases.set_activity_sharing_use_case import (
    SetActivitySharingUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
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

CUANDO = datetime(2026, 8, 10, 12, 0)

# Un tipo de cada publico para el test: el mapa real los tiene todos en BOTH
SOLO_AUTOR = ActivityEventType.BIRDIE
SOLO_AMIGOS = ActivityEventType.EAGLE_OR_BETTER
AMBOS = ActivityEventType.HOLE_IN_ONE

# Los seis logros: los avisos de BE-2 tienen su propio publico
TODOS_LOS_LOGROS = [t for t in ActivityEventType if t.is_achievement]


def _todos(*user_ids) -> ActivitySlice:
    """Todo lo de esos jugadores, de cualquier tipo y visibilidad."""
    return ActivitySlice(user_ids=tuple(user_ids), types=frozenset(ActivityEventType))


@pytest.fixture
def publicos(monkeypatch):
    monkeypatch.setitem(AUDIENCE_BY_TYPE, SOLO_AUTOR, ActivityAudience.SELF)
    monkeypatch.setitem(AUDIENCE_BY_TYPE, SOLO_AMIGOS, ActivityAudience.FRIENDS)
    monkeypatch.setitem(AUDIENCE_BY_TYPE, AMBOS, ActivityAudience.BOTH)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _create_user(user_uow) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"aud_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amigos(social_uow, a: User, b: User) -> Friendship:
    friendship = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)
    return friendship


async def _publica(
    social_uow,
    user: User,
    tipo: ActivityEventType,
    match_id: str | None = None,
    visible_to_friends: bool = True,
    publicado: datetime = CUANDO,
) -> str:
    match_id = match_id or f"{tipo.value}-{uuid4().hex[:6]}"
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=user.id,
                    type=tipo,
                    occurred_at=publicado,
                    source_match_id=match_id,
                    published_at=publicado,
                    visible_to_friends=visible_to_friends,
                )
            ]
        )
    return match_id


async def _feed_de(social_uow, user_uow, user: User) -> set[str]:
    feed = await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(user.id.value))
    return {e.source_match_id for e in feed.events}


async def _actividad(social_uow, user_uow, viewer: User, target: User) -> set[str]:
    resultado = await GetPlayerActivityUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(viewer.id.value), str(target.id.value))
    return {e.source_match_id for e in resultado.events}


async def _sharing(social_uow, user_uow, user: User, enabled: bool) -> int:
    return await SetActivitySharingUseCase(user_uow, social_uow).execute(
        str(user.id.value), enabled=enabled
    )


@pytest.mark.usefixtures("publicos")
class TestPublicoDeCadaTipo:
    async def test_d17_un_evento_self_solo_lo_ve_su_autor(self, social_uow, user_uow):
        """
        D17. Given un evento SELF mio / When lo buscan mi feed, el de mi amigo y
        mi actividad vista por el / Then solo sale en lo mio.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        aviso = await _publica(social_uow, yo, SOLO_AUTOR)

        assert aviso in await _feed_de(social_uow, user_uow, yo)
        assert aviso in await _actividad(social_uow, user_uow, yo, yo)
        assert aviso not in await _feed_de(social_uow, user_uow, amigo)
        assert aviso not in await _actividad(social_uow, user_uow, amigo, yo)

    async def test_d18_un_evento_friends_lo_ven_mis_amigos_y_no_yo(self, social_uow, user_uow):
        """
        D18. Given un evento FRIENDS mio / When lo buscan / Then sale en el feed
        de mi amigo y en mi actividad vista por el, pero no en mi feed.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        apuntado = await _publica(social_uow, yo, SOLO_AMIGOS)

        assert apuntado in await _feed_de(social_uow, user_uow, amigo)
        assert apuntado in await _actividad(social_uow, user_uow, amigo, yo)
        assert apuntado not in await _feed_de(social_uow, user_uow, yo)

    async def test_d19_un_evento_both_lo_vemos_los_dos(self, social_uow, user_uow):
        """D19. Given un evento BOTH mio / When lo buscan / Then sale en los dos feeds."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        hoyo = await _publica(social_uow, yo, AMBOS)

        assert hoyo in await _feed_de(social_uow, user_uow, yo)
        assert hoyo in await _feed_de(social_uow, user_uow, amigo)
        assert hoyo in await _actividad(social_uow, user_uow, amigo, yo)

    async def test_un_extranio_no_ve_nada_de_ningun_publico(self, social_uow, user_uow):
        """Given eventos de los tres publicos / When un no amigo pide su feed / Then nada."""
        yo = await _create_user(user_uow)
        extranio = await _create_user(user_uow)
        for tipo in (SOLO_AUTOR, SOLO_AMIGOS, AMBOS):
            await _publica(social_uow, yo, tipo)

        assert await _feed_de(social_uow, user_uow, extranio) == set()


@pytest.mark.usefixtures("publicos")
class TestInterruptor:
    async def test_d20_apagar_retira_a_los_amigos_y_conserva_lo_mio(self, social_uow, user_uow):
        """
        D20. Given eventos SELF, FRIENDS y BOTH / When apago la publicacion /
        Then el FRIENDS desaparece, el BOTH queda solo para mi y el SELF sigue.

        El BOTH no se borra: el interruptor decide lo que ven los demas, no lo
        que guarda uno de si mismo.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        aviso = await _publica(social_uow, yo, SOLO_AUTOR)
        apuntado = await _publica(social_uow, yo, SOLO_AMIGOS)
        hoyo = await _publica(social_uow, yo, AMBOS)

        retirados = await _sharing(social_uow, user_uow, yo, enabled=False)

        assert retirados == 2
        assert await _feed_de(social_uow, user_uow, yo) == {aviso, hoyo}
        async with social_uow:
            mios = await social_uow.activity_events.find_in([_todos(yo.id)], limit=50)
        assert apuntado not in {e.source_match_id for e in mios}
        # Volver a encenderlo no lo destapa: se retiro y se queda retirado
        await _sharing(social_uow, user_uow, yo, enabled=True)
        assert hoyo not in await _feed_de(social_uow, user_uow, amigo)
        assert hoyo not in await _actividad(social_uow, user_uow, amigo, yo)

    async def test_d20a_un_logro_publicado_con_el_interruptor_apagado_solo_es_mio(
        self, social_uow, user_uow
    ):
        """
        D20a. Given la publicacion apagada / When se publica un BOTH oculto /
        Then lo veo yo y mi amigo no.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _sharing(social_uow, user_uow, yo, enabled=False)

        hoyo = await _publica(social_uow, yo, AMBOS, visible_to_friends=False)

        assert hoyo in await _feed_de(social_uow, user_uow, yo)
        assert hoyo not in await _feed_de(social_uow, user_uow, amigo)

    async def test_d20b_encender_otra_vez_no_destapa_lo_publicado_apagado(
        self, social_uow, user_uow
    ):
        """
        D20b. Given un logro publicado con la publicacion apagada / When la
        vuelvo a encender / Then mi amigo sigue sin verlo, ni en su feed ni en
        mi actividad.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _sharing(social_uow, user_uow, yo, enabled=False)
        hoyo = await _publica(social_uow, yo, AMBOS, visible_to_friends=False)

        await _sharing(social_uow, user_uow, yo, enabled=True)

        assert hoyo not in await _feed_de(social_uow, user_uow, amigo)
        assert hoyo not in await _actividad(social_uow, user_uow, amigo, yo)
        assert hoyo in await _feed_de(social_uow, user_uow, yo)

    async def test_d20c_lo_publicado_tras_encender_si_lo_ven_mis_amigos(self, social_uow, user_uow):
        """
        D20c. Given la publicacion apagada y vuelta a encender / When se publica
        un logro nuevo / Then mi amigo lo ve.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _sharing(social_uow, user_uow, yo, enabled=False)
        await _sharing(social_uow, user_uow, yo, enabled=True)

        hoyo = await _publica(social_uow, yo, AMBOS, publicado=CUANDO + timedelta(days=1))

        assert hoyo in await _feed_de(social_uow, user_uow, amigo)
        assert hoyo in await _actividad(social_uow, user_uow, amigo, yo)


@pytest.mark.usefixtures("publicos")
class TestBloqueo:
    async def test_d21_bloqueados_no_ven_nada_el_uno_del_otro(self, social_uow, user_uow):
        """
        D21. Given dos amigos con eventos de todos los publicos / When uno
        bloquea al otro / Then ninguno ve nada del otro, ni en el feed ni en la
        actividad.
        """
        yo = await _create_user(user_uow)
        otro = await _create_user(user_uow)
        amistad = await _amigos(social_uow, yo, otro)
        mios = {await _publica(social_uow, yo, t) for t in (SOLO_AUTOR, SOLO_AMIGOS, AMBOS)}
        suyos = {await _publica(social_uow, otro, t) for t in (SOLO_AUTOR, SOLO_AMIGOS, AMBOS)}

        amistad.block(yo.id)

        assert not (await _feed_de(social_uow, user_uow, otro)) & mios
        assert not (await _feed_de(social_uow, user_uow, yo)) & suyos
        with pytest.raises(ActivityNotVisibleError):
            await _actividad(social_uow, user_uow, otro, yo)
        with pytest.raises(ActivityNotVisibleError):
            await _actividad(social_uow, user_uow, yo, otro)


class TestLogrosDeSiempre:
    @pytest.mark.parametrize("tipo", TODOS_LOS_LOGROS)
    async def test_d22_cada_logro_sigue_como_antes(self, social_uow, user_uow, tipo):
        """
        D22. Given un logro de los seis de siempre, con el mapa real / When lo
        buscan / Then sale en mi feed, en el de mi amigo y en mi actividad
        vista por el; y al apagar la publicacion deja de verlo el.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        logro = await _publica(social_uow, yo, tipo)

        assert logro in await _feed_de(social_uow, user_uow, yo)
        assert logro in await _feed_de(social_uow, user_uow, amigo)
        assert logro in await _actividad(social_uow, user_uow, amigo, yo)

        await _sharing(social_uow, user_uow, yo, enabled=False)

        assert logro not in await _feed_de(social_uow, user_uow, amigo)
        assert logro in await _feed_de(social_uow, user_uow, yo)
