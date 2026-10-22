"""
Un torneo que AHORA es privado no se enseña como «X se ha apuntado», aunque
fallara el borrado de su aviso (tabla del 22 oct 2026, E).

| Caso                                                        | Resultado              |
|-------------------------------------------------------------|------------------------|
| Apuntado a uno que ahora es privado, en el feed de un amigo | No sale                |
| Apuntado a uno publico                                      | Sale                   |
| Lo mismo en la actividad de su perfil                       | No sale                |
| Pagina llena con uno oculto                                 | El cursor sigue igual: |
|                                                             | nada se pierde ni se   |
|                                                             | repite                 |
| Toda la pagina se pregunta de una vez                       | Una consulta por pagina|
| Otros avisos de ese torneo (SELF)                           | Siguen                 |
| Sin el puerto (cableado viejo)                              | No se filtra           |
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.ports.tournament_visibility_interface import (
    TournamentVisibilityInterface,
)
from src.modules.social.application.use_cases.get_feed_unseen_count_use_case import (
    GetFeedUnseenCountUseCase,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
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

T = ActivityEventType
AHORA = datetime(2026, 10, 22, 12, 0)
PRIVADO = str(uuid4())
PUBLICO = str(uuid4())


class _Torneos(TournamentVisibilityInterface):
    """Que torneos son privados ahora; apunta cada pregunta."""

    def __init__(self, privados: set[str]):
        self._privados = privados
        self.preguntas: list[list[str]] = []

    async def private_ids(self, competition_ids: Sequence[str]) -> set[str]:
        self.preguntas.append(sorted(competition_ids))
        return {c for c in competition_ids if c in self._privados}


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def torneos():
    return _Torneos({PRIVADO})


async def _user(user_uow, nombre: str) -> User:
    user = User.create(
        first_name=nombre,
        last_name="Garcia",
        email_str=f"priv_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amigos(social_uow, a: User, b: User) -> None:
    amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    amistad.accept()
    async with social_uow:
        await social_uow.friendships.add(amistad)


async def _evento(
    social_uow, user: User, tipo: ActivityEventType, competition_id: str, minuto: int
) -> ActivityEvent:
    evento = ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=AHORA,
        source_match_id=competition_id if tipo.value.startswith("ENROLLED") else str(uuid4()),
        payload={"competition_id": competition_id, "competition_name": "Copa"},
        published_at=AHORA + timedelta(minutes=minuto),
    )
    async with social_uow:
        await social_uow.activity_events.add_many([evento])
    return evento


def _feed(social_uow, user_uow, torneos=None) -> GetFriendsFeedUseCase:
    return GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork(), tournaments=torneos
    )


def _actividad(social_uow, user_uow, torneos=None) -> GetPlayerActivityUseCase:
    return GetPlayerActivityUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork(), tournaments=torneos
    )


@pytest.fixture
async def pareja(social_uow, user_uow):
    yo = await _user(user_uow, "Yo")
    amigo = await _user(user_uow, "Amigo")
    await _amigos(social_uow, yo, amigo)
    return yo, amigo


class TestFeed:
    async def test_e_apuntado_a_uno_ahora_privado_no_sale(
        self, social_uow, user_uow, torneos, pareja
    ):
        yo, amigo = pareja
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PRIVADO, 1)
        publico = await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PUBLICO, 2)

        feed = await _feed(social_uow, user_uow, torneos).execute(str(yo.id.value))

        assert [e.id for e in feed.events] == [str(publico.id)]

    async def test_e_los_avisos_propios_de_ese_torneo_siguen(
        self, social_uow, user_uow, torneos, pareja
    ):
        """Solo se oculta «X se ha apuntado»: mi «ya estas inscrito» es mio y sigue."""
        yo, amigo = pareja
        mio = await _evento(social_uow, yo, T.ENROLLMENT_CONFIRMED, PRIVADO, 1)
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PRIVADO, 2)

        feed = await _feed(social_uow, user_uow, torneos).execute(str(yo.id.value))

        assert [e.id for e in feed.events] == [str(mio.id)]

    async def test_e_una_sola_pregunta_por_pagina(self, social_uow, user_uow, torneos, pareja):
        yo, amigo = pareja
        for minuto in range(4):
            await _evento(
                social_uow,
                amigo,
                T.ENROLLED_IN_TOURNAMENT,
                PRIVADO if minuto % 2 else str(uuid4()),
                minuto,
            )

        await _feed(social_uow, user_uow, torneos).execute(str(yo.id.value))

        assert len(torneos.preguntas) == 1
        assert len(torneos.preguntas[0]) == 3

    async def test_e_sin_apuntados_no_se_pregunta(self, social_uow, user_uow, torneos, pareja):
        yo, amigo = pareja
        await _evento(social_uow, amigo, T.BIRDIE, PRIVADO, 1)

        feed = await _feed(social_uow, user_uow, torneos).execute(str(yo.id.value))

        assert len(feed.events) == 1
        assert torneos.preguntas == []

    async def test_e_el_cursor_no_pierde_ni_repite_nada(
        self, social_uow, user_uow, torneos, pareja
    ):
        """
        Given 5 entradas y la 2.ª mas reciente oculta / When pido paginas de 2 /
        Then salen las otras 4, cada una una vez, y en orden.
        """
        yo, amigo = pareja
        visibles = []
        for minuto in range(5):
            torneo = PRIVADO if minuto == 3 else str(uuid4())
            evento = await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, torneo, minuto)
            if torneo != PRIVADO:
                visibles.append(str(evento.id))

        vistas, cursor = [], None
        for _ in range(5):
            pagina = await _feed(social_uow, user_uow, torneos).execute(
                str(yo.id.value), limit=2, cursor=cursor
            )
            vistas.extend(e.id for e in pagina.events)
            cursor = pagina.next_cursor
            if cursor is None:
                break

        assert vistas == list(reversed(visibles))

    async def test_e_sin_el_puerto_no_se_filtra(self, social_uow, user_uow, pareja):
        yo, amigo = pareja
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PRIVADO, 1)

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert len(feed.events) == 1


class TestActividadDelPerfil:
    async def test_e_apuntado_a_uno_ahora_privado_no_sale(
        self, social_uow, user_uow, torneos, pareja
    ):
        yo, amigo = pareja
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PRIVADO, 1)
        publico = await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PUBLICO, 2)

        actividad = await _actividad(social_uow, user_uow, torneos).execute(
            str(yo.id.value), str(amigo.id.value)
        )

        assert [e.id for e in actividad.events] == [str(publico.id)]

    async def test_e_el_cursor_sigue_aunque_la_pagina_quede_corta(
        self, social_uow, user_uow, torneos, pareja
    ):
        """Una pagina llena con una oculta trae cursor: detras hay mas."""
        yo, amigo = pareja
        primera = await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, str(uuid4()), 0)
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PRIVADO, 1)
        ultima = await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PUBLICO, 2)

        caso = _actividad(social_uow, user_uow, torneos)
        pagina = await caso.execute(str(yo.id.value), str(amigo.id.value), limit=2)
        assert [e.id for e in pagina.events] == [str(ultima.id)]
        assert pagina.next_cursor is not None

        siguiente = await caso.execute(
            str(yo.id.value), str(amigo.id.value), limit=2, cursor=pagina.next_cursor
        )
        assert [e.id for e in siguiente.events] == [str(primera.id)]
        assert siguiente.next_cursor is None


class TestContador:
    """Revision: el numero del boton no cuenta lo que la regla E oculta al leer."""

    async def test_e_el_contador_no_cuenta_los_apuntados_a_privados(
        self, social_uow, user_uow, torneos, pareja
    ):
        yo, amigo = pareja
        # El repositorio en memoria no conoce los torneos: se le dice cuales son privados
        social_uow.activity_events.private_competition_ids = {PRIVADO}
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PRIVADO, 1)
        await _evento(social_uow, amigo, T.ENROLLED_IN_TOURNAMENT, PUBLICO, 2)
        # Mi «ya estas inscrito» del privado si cuenta: es mio
        await _evento(social_uow, yo, T.ENROLLMENT_CONFIRMED, PRIVADO, 3)

        contador = await GetFeedUnseenCountUseCase(social_uow, user_uow).execute(str(yo.id.value))
        feed = await _feed(social_uow, user_uow, torneos).execute(str(yo.id.value))

        assert contador.unseen_count == 2
        assert feed.unseen_count == 2
        assert len(feed.events) == 2
