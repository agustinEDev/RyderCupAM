"""
La llave de una privada (tabla del 27 oct 2026, filas 9 y 10): quien está
fuera ve lo jugado de un amigo si en SU Actividad le sale un evento de ese
amigo en esa competición. La regla es la del feed: amigos que publican, tipos
que ven los amigos y lo no oculto. «Se ha apuntado» a una privada no cuenta:
el feed ya no lo enseña.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.adapters.eventos_de_amigos_adapter import (
    EventosDeAmigosAdapter,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

T = ActivityEventType
CUANDO = datetime(2026, 10, 20, 12, 0)


class _Mundo:
    def __init__(self):
        self.social = InMemorySocialUnitOfWork()
        self.users = InMemoryUserUnitOfWork()
        self.torneo = CompetitionId(uuid4())

    async def usuario(self, *, comparte: bool = True) -> User:
        user = User.create(
            first_name="Ana",
            last_name="Llave",
            email_str=f"llave_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        if not comparte:
            user.set_activity_sharing(False)
        async with self.users:
            await self.users.users.save(user)
        return user

    async def amigos(self, a: User, b: User) -> None:
        amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
        amistad.accept()
        async with self.social:
            await self.social.friendships.add(amistad)

    async def evento(self, user: User, tipo=T.BIRDIE, *, torneo=None, visible=True) -> None:
        payload = {"competition_id": str((torneo or self.torneo).value), "from_tournament": True}
        async with self.social:
            await self.social.activity_events.add_many(
                [
                    ActivityEvent.create(
                        user_id=user.id,
                        type=tipo,
                        occurred_at=CUANDO,
                        source_match_id=f"m-{uuid4().hex[:6]}",
                        payload=payload,
                        published_at=CUANDO,
                        visible_to_friends=visible,
                    )
                ]
            )

    async def llave(self, yo: User, torneo=None):
        return await EventosDeAmigosAdapter(self.social, self.users).amigos_con_evento_en(
            yo.id, torneo or self.torneo
        )


@pytest.fixture
def m() -> _Mundo:
    return _Mundo()


@pytest.mark.parametrize(
    "tipo",
    [T.BIRDIE, T.EAGLE_OR_BETTER, T.HOLE_IN_ONE, T.NEW_COURSE, T.PERSONAL_BEST, T.FIRST_TOURNAMENT],
)
async def test_9_un_logro_de_un_amigo_en_ese_torneo_abre(m, tipo):
    yo, amigo = await m.usuario(), await m.usuario()
    await m.amigos(yo, amigo)
    await m.evento(amigo, tipo)

    assert await m.llave(yo) == frozenset({amigo.id})


async def test_10_su_posicion_final_tambien_abre(m):
    yo, amigo = await m.usuario(), await m.usuario()
    await m.amigos(amigo, yo)
    await m.evento(amigo, T.TOURNAMENT_FINAL_STANDING)

    assert await m.llave(yo) == frozenset({amigo.id})


async def test_solo_los_amigos_con_evento(m):
    yo, con_evento, sin_evento = await m.usuario(), await m.usuario(), await m.usuario()
    await m.amigos(yo, con_evento)
    await m.amigos(yo, sin_evento)
    await m.evento(con_evento)

    assert await m.llave(yo) == frozenset({con_evento.id})


async def test_9_de_otro_torneo_no_abre(m):
    yo, amigo = await m.usuario(), await m.usuario()
    await m.amigos(yo, amigo)
    await m.evento(amigo, torneo=CompetitionId(uuid4()))

    assert await m.llave(yo) == frozenset()


async def test_9_de_alguien_que_no_es_su_amigo_no_abre(m):
    yo, ajeno = await m.usuario(), await m.usuario()
    await m.evento(ajeno)

    assert await m.llave(yo) == frozenset()


async def test_9_si_su_amigo_no_comparte_actividad_no_abre(m):
    yo, amigo = await m.usuario(), await m.usuario(comparte=False)
    await m.amigos(yo, amigo)
    await m.evento(amigo)

    assert await m.llave(yo) == frozenset()


async def test_9_un_evento_oculto_no_abre(m):
    yo, amigo = await m.usuario(), await m.usuario()
    await m.amigos(yo, amigo)
    await m.evento(amigo, visible=False)

    assert await m.llave(yo) == frozenset()


@pytest.mark.parametrize(
    "tipo",
    [
        # El feed ya no enseña «se ha apuntado» a una privada
        T.ENROLLED_IN_TOURNAMENT,
        # Solo de su autor: a sus amigos no les llegan
        T.TOURNAMENT_MATCH_RESULT,
        T.TEE_TIME_ASSIGNED,
        T.ENROLLMENT_APPROVED,
    ],
)
async def test_9_lo_que_no_le_sale_en_actividad_no_abre(m, tipo):
    yo, amigo = await m.usuario(), await m.usuario()
    await m.amigos(yo, amigo)
    await m.evento(amigo, tipo)

    assert await m.llave(yo) == frozenset()


async def test_su_propio_evento_no_es_la_llave(m):
    """Lo suyo ya lo ve: si jugó, está dentro; si no, su evento no le abre nada."""
    yo = await m.usuario()
    await m.evento(yo)

    assert await m.llave(yo) == frozenset()


async def test_sin_amigos_ni_se_pregunta_por_los_eventos(m):
    yo = await m.usuario()

    assert await m.llave(yo) == frozenset()
