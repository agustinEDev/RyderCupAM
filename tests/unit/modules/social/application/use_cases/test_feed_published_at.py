"""
Tests del feed ordenado y contado por fecha de publicacion.

`occurred_at` dice cuando se jugo; `published_at`, cuando llego al feed. Un
torneo publica al cerrarse vueltas de hace dias, y una partida rapida se fecha
cuando se creo aunque se cierre horas despues: comparar `occurred_at` con la
ultima visita dejaba fuera del aviso casi todo lo de los torneos.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.feed_cursor import build_cursor
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
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

VISITA = datetime(2026, 8, 10, 12, 0)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _create_user(user_uow, visto: datetime | None = None) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"pub_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if visto is not None:
        user.mark_feed_as_seen(visto)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amigos(social_uow, a: User, b: User) -> None:
    friendship = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)


def _evento(
    user: User,
    match_id: str,
    jugado: datetime,
    publicado: datetime,
    tipo: ActivityEventType = ActivityEventType.BIRDIE,
    id: UUID | None = None,
) -> ActivityEvent:
    return ActivityEvent.reconstruct(
        id=id or uuid4(),
        user_id=user.id,
        type=tipo,
        occurred_at=jugado,
        source_match_id=match_id,
        payload={},
        published_at=publicado,
        visible_to_friends=True,
    )


async def _publica(social_uow, *eventos: ActivityEvent) -> None:
    async with social_uow:
        await social_uow.activity_events.add_many(list(eventos))


def _feed(social_uow, user_uow) -> GetFriendsFeedUseCase:
    return GetFriendsFeedUseCase(social_uow, user_uow, InMemoryGolfCourseUnitOfWork())


async def _recorre(use_case, viewer: User, limit: int, cursor: str | None = None):
    vistos, paginas = [], 0
    while True:
        pagina = await use_case.execute(str(viewer.id.value), limit=limit, cursor=cursor)
        vistos.extend(pagina.events)
        paginas += 1
        cursor = pagina.next_cursor
        if cursor is None or paginas > 50:
            return vistos


class TestElAvisoCuentaPorPublicacion:
    async def test_a1_torneo_publicado_tras_la_visita_cuenta_aunque_se_jugara_dias_antes(
        self, social_uow, user_uow
    ):
        """
        A1. Given un torneo cuyas vueltas se jugaron tres dias antes de mi
        ultima visita / When se publica despues de ella / Then cuenta como
        novedad: lo nuevo es la publicacion, no la vuelta.
        """
        yo = await _create_user(user_uow, visto=VISITA)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _publica(
            social_uow,
            _evento(amigo, "torneo-1", VISITA - timedelta(days=3), VISITA + timedelta(hours=1)),
        )

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.unseen_count == 1

    async def test_a2_partida_rapida_empezada_antes_y_publicada_despues_cuenta(
        self, social_uow, user_uow
    ):
        """
        A2. Given una partida rapida creada antes de mi visita / When se cierra
        y publica despues / Then cuenta como novedad.
        """
        yo = await _create_user(user_uow, visto=VISITA)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _publica(
            social_uow,
            _evento(amigo, "rapida-1", VISITA - timedelta(hours=2), VISITA + timedelta(minutes=5)),
        )

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.unseen_count == 1

    async def test_a3_lo_publicado_antes_de_la_visita_no_cuenta(self, social_uow, user_uow):
        """
        A3. Given un logro publicado antes de mi visita aunque jugado un rato
        antes / When pido el feed / Then no cuenta: ya estaba cuando mire.
        """
        yo = await _create_user(user_uow, visto=VISITA)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _publica(
            social_uow,
            _evento(amigo, "viejo", VISITA - timedelta(hours=3), VISITA - timedelta(minutes=1)),
        )

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.unseen_count == 0


class TestOrdenYCursor:
    async def test_a6_el_feed_se_ordena_por_publicacion_y_no_por_juego(self, social_uow, user_uow):
        """
        A6. Given un torneo jugado hace dias y publicado hoy, y una partida
        jugada ayer y publicada ayer / When pido el feed / Then el torneo va
        primero: es lo ultimo que ha llegado.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        await _publica(
            social_uow,
            _evento(amigo, "torneo", VISITA - timedelta(days=5), VISITA),
            _evento(amigo, "ayer", VISITA - timedelta(days=1), VISITA - timedelta(days=1)),
        )

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert [e.source_match_id for e in feed.events] == ["torneo", "ayer"]

    async def test_el_evento_del_feed_lleva_su_fecha_de_publicacion(self, social_uow, user_uow):
        """Given un logro publicado / When pido el feed / Then viaja su `published_at`."""
        yo = await _create_user(user_uow)
        await _publica(social_uow, _evento(yo, "mio", VISITA - timedelta(days=2), VISITA))

        feed = await _feed(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.events[0].published_at == VISITA
        assert feed.events[0].occurred_at == VISITA - timedelta(days=2)

    async def test_el_cursor_sale_de_la_fecha_de_publicacion(self, social_uow, user_uow):
        """
        Given una pagina llena / When se construye el cursor / Then lleva la
        fecha de publicacion del ultimo, que es por la que se ordena.
        """
        yo = await _create_user(user_uow)
        evento = _evento(yo, "mio", VISITA - timedelta(days=2), VISITA)

        cursor = build_cursor([evento], limit=1)

        assert cursor == f"{VISITA.isoformat()}|{evento.id}"

    async def test_a4_misma_publicacion_orden_estable_por_id_sin_repetir_ni_saltar(
        self, social_uow, user_uow
    ):
        """
        A4. Given siete logros publicados en el mismo instante (los de una
        vuelta) / When paso paginas de 3 / Then salen los siete, una vez cada
        uno y ordenados por id de mayor a menor.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        eventos = [
            _evento(amigo, f"match-{i}", VISITA - timedelta(days=i), VISITA) for i in range(7)
        ]
        await _publica(social_uow, *eventos)

        vistos = await _recorre(_feed(social_uow, user_uow), yo, limit=3)

        assert len(vistos) == 7
        assert len({e.id for e in vistos}) == 7
        assert [e.id for e in vistos] == sorted((str(e.id) for e in eventos), reverse=True)

    async def test_a5_un_cursor_de_antes_del_cambio_sigue_valiendo(self, social_uow, user_uow):
        """
        A5. Given eventos de antes del cambio (su `published_at` se relleno con
        su `occurred_at`) y un cursor emitido entonces, con `occurred_at|id` /
        When se pide la pagina siguiente con el / Then continua justo detras,
        sin repetir ni saltarse nada.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _amigos(social_uow, yo, amigo)
        viejos = [
            _evento(amigo, f"viejo-{i}", VISITA - timedelta(days=i), VISITA - timedelta(days=i))
            for i in range(4)
        ]
        await _publica(social_uow, *viejos)
        # El cursor que el cliente guardo antes del cambio: fecha de juego e id
        # del segundo evento, el ultimo de una pagina de 2
        cursor_viejo = f"{viejos[1].occurred_at.isoformat()}|{viejos[1].id}"

        pagina = await _feed(social_uow, user_uow).execute(
            str(yo.id.value), limit=2, cursor=cursor_viejo
        )

        assert [e.source_match_id for e in pagina.events] == ["viejo-2", "viejo-3"]
