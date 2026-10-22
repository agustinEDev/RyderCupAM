"""
Un «Te han invitado» de una invitacion que ya no se puede aceptar no se enseña
ni cuenta (revision final, 22 oct 2026).

La invitacion puede caducar sola sin que nadie la toque, y entonces nadie
retira su aviso. Al leer, el feed, la actividad del perfil y el contador
preguntan por las invitaciones de la pagina —por el id que es el origen del
aviso— y ocultan las que no estan pendientes o ya caducaron. Como el filtro de
torneos privados: por lotes, con el cursor calculado antes de filtrar.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.ports.invitation_availability_interface import (
    InvitationAvailabilityInterface,
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
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
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
CERRADA = str(uuid4())
ABIERTA = str(uuid4())


class _Invitaciones(InvitationAvailabilityInterface):
    """Que invitaciones ya no se pueden aceptar; apunta cada pregunta."""

    def __init__(self, cerradas: set[str]):
        self._cerradas = cerradas
        self.preguntas: list[list[str]] = []

    async def closed_ids(self, invitation_ids: Sequence[str]) -> set[str]:
        self.preguntas.append(sorted(invitation_ids))
        return {i for i in invitation_ids if i in self._cerradas}


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def invitaciones():
    return _Invitaciones({CERRADA})


@pytest.fixture
async def yo(user_uow):
    user = User.create(
        first_name="Yo",
        last_name="Garcia",
        email_str=f"inv_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _evento(social_uow, user: User, tipo: ActivityEventType, origen: str, minuto: int):
    evento = ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=AHORA,
        source_match_id=origen,
        payload={"competition_id": str(uuid4()), "competition_name": "Copa"},
        published_at=AHORA + timedelta(minutes=minuto),
    )
    async with social_uow:
        await social_uow.activity_events.add_many([evento])
    return evento


def _feed(social_uow, user_uow, invitaciones=None) -> GetFriendsFeedUseCase:
    return GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork(), invitations=invitaciones
    )


class TestFeed:
    async def test_la_invitacion_cerrada_no_sale_y_la_abierta_si(
        self, social_uow, user_uow, invitaciones, yo
    ):
        await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, CERRADA, 1)
        abierta = await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, ABIERTA, 2)

        feed = await _feed(social_uow, user_uow, invitaciones).execute(str(yo.id.value))

        assert [e.id for e in feed.events] == [str(abierta.id)]

    async def test_solo_se_ocultan_las_invitaciones(self, social_uow, user_uow, invitaciones, yo):
        """Otro aviso con ese mismo origen no es una invitacion: sigue."""
        otro = await _evento(social_uow, yo, T.ENROLLMENT_APPROVED, CERRADA, 1)
        await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, CERRADA, 2)

        feed = await _feed(social_uow, user_uow, invitaciones).execute(str(yo.id.value))

        assert [e.id for e in feed.events] == [str(otro.id)]

    async def test_una_sola_pregunta_por_pagina(self, social_uow, user_uow, invitaciones, yo):
        for minuto in range(3):
            await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, str(uuid4()), minuto)

        await _feed(social_uow, user_uow, invitaciones).execute(str(yo.id.value))

        assert len(invitaciones.preguntas) == 1
        assert len(invitaciones.preguntas[0]) == 3

    async def test_sin_invitaciones_no_se_pregunta(self, social_uow, user_uow, invitaciones, yo):
        await _evento(social_uow, yo, T.ENROLLMENT_APPROVED, str(uuid4()), 1)

        await _feed(social_uow, user_uow, invitaciones).execute(str(yo.id.value))

        assert invitaciones.preguntas == []

    async def test_el_cursor_no_pierde_ni_repite_nada(self, social_uow, user_uow, invitaciones, yo):
        visibles = []
        for minuto in range(5):
            origen = CERRADA if minuto == 3 else str(uuid4())
            evento = await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, origen, minuto)
            if origen != CERRADA:
                visibles.append(str(evento.id))

        vistas, cursor = [], None
        for _ in range(5):
            pagina = await _feed(social_uow, user_uow, invitaciones).execute(
                str(yo.id.value), limit=2, cursor=cursor
            )
            vistas.extend(e.id for e in pagina.events)
            cursor = pagina.next_cursor
            if cursor is None:
                break

        assert vistas == list(reversed(visibles))

    async def test_sin_el_puerto_no_se_filtra(self, social_uow, user_uow, yo):
        await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, CERRADA, 1)

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert len(feed.events) == 1


class TestActividadDelPerfil:
    async def test_mi_invitacion_cerrada_no_sale_en_mi_actividad(
        self, social_uow, user_uow, invitaciones, yo
    ):
        await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, CERRADA, 1)
        abierta = await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, ABIERTA, 2)

        actividad = await GetPlayerActivityUseCase(
            social_uow, user_uow, InMemoryGolfCourseUnitOfWork(), invitations=invitaciones
        ).execute(str(yo.id.value), str(yo.id.value))

        assert [e.id for e in actividad.events] == [str(abierta.id)]


class TestContador:
    async def test_el_contador_no_cuenta_las_cerradas(self, social_uow, user_uow, invitaciones, yo):
        # El repositorio en memoria no conoce las invitaciones: se le dicen las abiertas
        social_uow.activity_events.open_invitation_ids = {ABIERTA}
        await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, CERRADA, 1)
        await _evento(social_uow, yo, T.INVITED_TO_TOURNAMENT, ABIERTA, 2)
        await _evento(social_uow, yo, T.ENROLLMENT_APPROVED, CERRADA, 3)

        contador = await GetFeedUnseenCountUseCase(social_uow, user_uow).execute(str(yo.id.value))
        feed = await _feed(social_uow, user_uow, invitaciones).execute(str(yo.id.value))

        assert contador.unseen_count == 2
        assert feed.unseen_count == 2
        assert len(feed.events) == 2
