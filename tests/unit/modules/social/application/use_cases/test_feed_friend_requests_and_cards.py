"""
Tests de las solicitudes de amistad en Actividad (BE-2, bloque F) y de los
logros de una vuelta en una sola tarjeta (E22).

Las solicitudes no son eventos: se leen en vivo de las amistades, asi que
aceptarla o rechazarla en otro sitio la quita sola.
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
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

VISITA = datetime(2026, 8, 10, 12, 0)
ANTES = VISITA - timedelta(hours=1)
DESPUES = VISITA + timedelta(hours=1)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _user(user_uow, nombre: str = "Ana", visto: datetime | None = VISITA) -> User:
    user = User.create(
        first_name=nombre,
        last_name="Garcia",
        email_str=f"req_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if visto is not None:
        user.mark_feed_as_seen(visto)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _solicitud(
    social_uow,
    de: User,
    a: User,
    cuando: datetime = DESPUES,
    status: FriendshipStatus = FriendshipStatus.PENDING,
) -> Friendship:
    amistad = Friendship.reconstruct(
        id=FriendshipId(uuid4()),
        requester_id=de.id,
        addressee_id=a.id,
        status=status,
        blocked_by=de.id if status == FriendshipStatus.BLOCKED else None,
        created_at=cuando,
        updated_at=cuando,
    )
    async with social_uow:
        await social_uow.friendships.add(amistad)
    return amistad


async def _feed(social_uow, user_uow, viewer: User, cursor: str | None = None):
    return await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork(), reloj=lambda: DESPUES
    ).execute(str(viewer.id.value), cursor=cursor)


async def _no_vistos(social_uow, user_uow, viewer: User) -> int:
    resultado = await GetFeedUnseenCountUseCase(
        social_uow, user_uow, reloj=lambda: DESPUES + timedelta(hours=1)
    ).execute(str(viewer.id.value))
    return resultado.unseen_count


class TestSolicitudesDeAmistad:
    async def test_f23_la_solicitud_recibida_sale_y_cuenta(self, social_uow, user_uow):
        """
        F23. Given Eva me pide amistad despues de mi ultima visita / When abro
        Actividad / Then sale su solicitud con quien la pide, y cuenta en el numero.
        """
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        amistad = await _solicitud(social_uow, eva, yo)

        feed = await _feed(social_uow, user_uow, yo)

        (solicitud,) = feed.pending_friend_requests
        assert solicitud.friendship_id == str(amistad.id.value)
        assert solicitud.requester.id == str(eva.id.value)
        assert solicitud.requester.first_name == "Eva"
        assert solicitud.created_at == DESPUES
        assert feed.unseen_count == 1
        assert await _no_vistos(social_uow, user_uow, yo) == 1

    async def test_f23_una_solicitud_de_antes_de_mi_visita_sale_pero_no_cuenta(
        self, social_uow, user_uow
    ):
        """F23. Given una solicitud vieja / When abro / Then sale, pero no es novedad."""
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        await _solicitud(social_uow, eva, yo, cuando=ANTES)

        feed = await _feed(social_uow, user_uow, yo)

        assert len(feed.pending_friend_requests) == 1
        assert feed.unseen_count == 0
        assert await _no_vistos(social_uow, user_uow, yo) == 0

    async def test_f23_sin_visita_previa_todas_cuentan(self, social_uow, user_uow):
        yo = await _user(user_uow, visto=None)
        eva = await _user(user_uow, "Eva")
        await _solicitud(social_uow, eva, yo, cuando=ANTES)

        assert await _no_vistos(social_uow, user_uow, yo) == 1

    async def test_f23_el_numero_sigue_con_tope_de_10(self, social_uow, user_uow):
        """F23. Given 12 solicitudes nuevas / When se cuenta / Then 10: el cliente pinta «9+»."""
        yo = await _user(user_uow)
        for i in range(12):
            otro = await _user(user_uow, f"Otro{i}")
            await _solicitud(social_uow, otro, yo)

        assert await _no_vistos(social_uow, user_uow, yo) == 10
        assert (await _feed(social_uow, user_uow, yo)).unseen_count == 10

    async def test_f24_aceptada_o_rechazada_desaparece(self, social_uow, user_uow):
        """
        F24. Given dos solicitudes / When una se acepta y otra se rechaza en otro
        sitio / Then ninguna sale ni cuenta.
        """
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        luz = await _user(user_uow, "Luz")
        aceptada = await _solicitud(social_uow, eva, yo)
        rechazada = await _solicitud(social_uow, luz, yo)
        aceptada.accept()
        rechazada.decline()
        async with social_uow:
            await social_uow.friendships.update(aceptada)
            await social_uow.friendships.update(rechazada)

        feed = await _feed(social_uow, user_uow, yo)

        assert feed.pending_friend_requests == []
        assert feed.unseen_count == 0

    async def test_f25_con_un_bloqueo_no_sale(self, social_uow, user_uow):
        """F25. Given un bloqueo entre los dos / When abro / Then no hay solicitud."""
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        await _solicitud(social_uow, eva, yo, status=FriendshipStatus.BLOCKED)

        feed = await _feed(social_uow, user_uow, yo)

        assert feed.pending_friend_requests == []
        assert await _no_vistos(social_uow, user_uow, yo) == 0

    async def test_f26_solo_las_recibidas_no_las_enviadas(self, social_uow, user_uow):
        """F26. Given una solicitud que envie yo / When abro / Then no sale en mi Actividad."""
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        await _solicitud(social_uow, yo, eva)

        feed = await _feed(social_uow, user_uow, yo)

        assert feed.pending_friend_requests == []
        assert feed.unseen_count == 0
        assert len((await _feed(social_uow, user_uow, eva)).pending_friend_requests) == 1


class TestUnaTarjetaPorVuelta:
    async def _logros(self, social_uow, user: User, partida: str, tipos) -> None:
        async with social_uow:
            await social_uow.activity_events.add_many(
                [
                    ActivityEvent.create(
                        user_id=user.id,
                        type=tipo,
                        occurred_at=DESPUES,
                        source_match_id=partida,
                        published_at=DESPUES,
                    )
                    for tipo in tipos
                ]
            )

    async def test_e22_varios_logros_de_una_vuelta_son_una_tarjeta(self, social_uow, user_uow):
        """
        E22. Given tres logros de una vuelta y uno de otra / When abro / Then
        los cuatro eventos, con la misma clave de tarjeta los de la vuelta, y el
        numero cuenta dos tarjetas.
        """
        yo = await _user(user_uow)
        await self._logros(
            social_uow,
            yo,
            "vuelta-1",
            [
                ActivityEventType.BIRDIE,
                ActivityEventType.EAGLE_OR_BETTER,
                ActivityEventType.NEW_COURSE,
            ],
        )
        await self._logros(social_uow, yo, "vuelta-2", [ActivityEventType.BIRDIE])

        feed = await _feed(social_uow, user_uow, yo)

        claves = {e.group_key for e in feed.events if e.source_match_id == "vuelta-1"}
        assert len(feed.events) == 4
        assert len(claves) == 1
        otra = next(e.group_key for e in feed.events if e.source_match_id == "vuelta-2")
        assert otra not in claves
        assert feed.unseen_count == 2
        assert await _no_vistos(social_uow, user_uow, yo) == 2

    async def test_e22_los_avisos_no_se_agrupan(self, social_uow, user_uow):
        """Given dos avisos del mismo origen / When abro / Then dos tarjetas."""
        yo = await _user(user_uow)
        await self._logros(
            social_uow,
            yo,
            "torneo-1",
            [ActivityEventType.ENROLLMENT_APPROVED, ActivityEventType.TOURNAMENT_FINAL_STANDING],
        )

        feed = await _feed(social_uow, user_uow, yo)

        assert len({e.group_key for e in feed.events}) == 2
        assert feed.unseen_count == 2

    async def test_e22_la_misma_vuelta_de_dos_jugadores_son_dos_tarjetas(
        self, social_uow, user_uow
    ):
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        amistad = Friendship.create(
            id=FriendshipId(uuid4()), requester_id=yo.id, addressee_id=eva.id
        )
        amistad.accept()
        async with social_uow:
            await social_uow.friendships.add(amistad)
        await self._logros(social_uow, yo, "vuelta-1", [ActivityEventType.BIRDIE])
        await self._logros(social_uow, eva, "vuelta-1", [ActivityEventType.BIRDIE])

        feed = await _feed(social_uow, user_uow, yo)

        assert len({e.group_key for e in feed.events}) == 2
        assert feed.unseen_count == 2


class TestRivalesConNombre:
    async def test_los_rivales_y_companeros_vienen_en_los_autores(self, social_uow, user_uow):
        """
        C13/D19. Given un resultado contra Eva con Luz de compañera / When abro
        / Then las dos vienen en `authors`, para pintar «a Eva» sin otra peticion.
        """
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        luz = await _user(user_uow, "Luz")
        pablo = await _user(user_uow, "Pablo")
        async with social_uow:
            await social_uow.activity_events.add_many(
                [
                    ActivityEvent.create(
                        user_id=yo.id,
                        type=ActivityEventType.TOURNAMENT_MATCH_RESULT,
                        occurred_at=DESPUES,
                        source_match_id="partido-1",
                        published_at=DESPUES,
                        payload={
                            "opponent_ids": [str(eva.id.value)],
                            "partner_ids": [str(luz.id.value)],
                        },
                    ),
                    ActivityEvent.create(
                        user_id=yo.id,
                        type=ActivityEventType.QUICK_MATCH_FINISHED,
                        occurred_at=DESPUES,
                        source_match_id="partida-1",
                        published_at=DESPUES,
                        payload={
                            "opponents": [
                                {"user_id": str(pablo.id.value), "name": None},
                                {"user_id": None, "name": "Seve Ballesteros"},
                            ],
                            "partners": [],
                        },
                    ),
                ]
            )

        feed = await _feed(social_uow, user_uow, yo)

        assert set(feed.authors) == {str(u.id.value) for u in (yo, eva, luz, pablo)}
        assert feed.authors[str(eva.id.value)].first_name == "Eva"


class TestPaginasSinPartirTarjetas:
    async def test_7_una_tarjeta_en_el_borde_de_la_pagina_va_entera(self, social_uow, user_uow):
        """
        7. Given un aviso reciente, una vuelta con tres logros y otro aviso mas
        viejo / When pido paginas de 2 / Then la primera trae el aviso y la
        vuelta entera, y la segunda sigue tras la vuelta sin repetir nada.
        """
        yo = await _user(user_uow)
        async with social_uow:
            await social_uow.activity_events.add_many(
                [
                    ActivityEvent.create(
                        user_id=yo.id,
                        type=ActivityEventType.ENROLLMENT_APPROVED,
                        occurred_at=DESPUES,
                        source_match_id="reciente",
                        published_at=DESPUES + timedelta(minutes=5),
                    ),
                    *[
                        ActivityEvent.create(
                            user_id=yo.id,
                            type=tipo,
                            occurred_at=DESPUES,
                            source_match_id="vuelta-1",
                            published_at=DESPUES,
                        )
                        for tipo in (
                            ActivityEventType.BIRDIE,
                            ActivityEventType.EAGLE_OR_BETTER,
                            ActivityEventType.NEW_COURSE,
                        )
                    ],
                    ActivityEvent.create(
                        user_id=yo.id,
                        type=ActivityEventType.ENROLLMENT_REJECTED,
                        occurred_at=DESPUES,
                        source_match_id="viejo",
                        published_at=DESPUES - timedelta(minutes=5),
                    ),
                ]
            )

        caso = GetFriendsFeedUseCase(
            social_uow, user_uow, InMemoryGolfCourseUnitOfWork(), reloj=lambda: DESPUES
        )
        primera = await caso.execute(str(yo.id.value), limit=2)
        segunda = await caso.execute(str(yo.id.value), limit=2, cursor=primera.next_cursor)
        actividad = GetPlayerActivityUseCase(social_uow, user_uow)
        mia = await actividad.execute(str(yo.id.value), str(yo.id.value), limit=2)

        assert [e.source_match_id for e in mia.events] == [
            e.source_match_id for e in primera.events
        ]

        assert [e.source_match_id for e in primera.events] == [
            "reciente",
            "vuelta-1",
            "vuelta-1",
            "vuelta-1",
        ]
        assert [e.source_match_id for e in segunda.events] == ["viejo"]
        assert segunda.next_cursor is None
