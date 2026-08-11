"""
Tests del feed de amigos (BE #176).

Dos reglas gobiernan estos tests: el feed solo enseña lo de los amigos
aceptados, y la privacidad se aplica **antes** de paginar — si se filtrara
despues, las paginas saldrian de tamaños irregulares.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
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
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

CUANDO = datetime(2026, 8, 10, 12, 0)
PAR = 4


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


async def _create_user(user_uow, share_activity: bool = True) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"feed_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _hacer_amigos(social_uow, a: User, b: User) -> Friendship:
    friendship = Friendship.create(
        id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id
    )
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)
    return friendship


async def _publica(
    social_uow,
    user: User,
    match_id: str,
    cuando: datetime = CUANDO,
    payload: dict | None = None,
):
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=user.id,
                    type=ActivityEventType.BIRDIE,
                    occurred_at=cuando,
                    source_match_id=match_id,
                    payload=payload,
                )
            ]
        )


async def _create_course(golf_course_uow, creator_id, name: str = "Test Golf Club"):
    """Campo de par 72: 18 hoyos de par 4."""
    course = GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
            Tee(
                category=TeeCategory.AMATEUR,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
            Tee(
                category=TeeCategory.CHAMPIONSHIP,
                gender=Gender.MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            ),
        ],
        holes=[Hole(number=i, par=PAR, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(course)
    return course


def _use_case(social_uow, user_uow, golf_course_uow=None):
    return GetFriendsFeedUseCase(
        social_uow, user_uow, golf_course_uow or InMemoryGolfCourseUnitOfWork()
    )


class TestQueSeVe:
    async def test_veo_los_logros_de_mis_amigos(self, social_uow, user_uow):
        """Given un amigo con un birdie / When pido el feed / Then sale."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert len(feed.events) == 1
        assert feed.events[0].source_match_id == "match-1"

    async def test_el_feed_trae_a_sus_autores(self, social_uow, user_uow):
        """
        Given un logro de un amigo / When pido el feed / Then viene quien lo
        publico, para no pedir un perfil por entrada.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert str(amigo.id.value) in feed.authors
        assert feed.authors[str(amigo.id.value)].first_name == "Ana"

    async def test_no_veo_los_logros_de_quien_no_es_mi_amigo(self, social_uow, user_uow):
        """Given un extranio con logros / When pido el feed / Then no sale nada."""
        yo = await _create_user(user_uow)
        extranio = await _create_user(user_uow)
        await _publica(social_uow, extranio, "match-1")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.events == []

    async def test_sin_amigos_ni_logros_propios_el_feed_llega_vacio(
        self, social_uow, user_uow
    ):
        """Given un jugador recien llegado / When pide el feed / Then llega vacio."""
        yo = await _create_user(user_uow)

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.events == []
        assert feed.next_cursor is None

    async def test_me_veo_a_mi_mismo_en_mi_feed(self, social_uow, user_uow):
        """
        Given un logro mio y otro de un amigo / When pido el feed / Then salen
        los dos: un feed donde no aparece lo que acabo de hacer se lee como si
        no se hubiera guardado.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, yo, "mio")
        await _publica(social_uow, amigo, "suyo", CUANDO - timedelta(days=1))

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert [e.source_match_id for e in feed.events] == ["mio", "suyo"]

    async def test_me_veo_aunque_no_tenga_amigos(self, social_uow, user_uow):
        """
        Given un jugador sin amigos pero con logros / When pide el feed / Then
        ve los suyos: el feed no nace vacio para quien aun no ha hecho amigos.
        """
        yo = await _create_user(user_uow)
        await _publica(social_uow, yo, "mio")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert [e.source_match_id for e in feed.events] == ["mio"]

    async def test_me_veo_aunque_tenga_la_publicacion_apagada(self, social_uow, user_uow):
        """
        Given que apague mi publicacion / When pido mi feed / Then sigo viendo
        lo mio: el interruptor decide lo que ven los demas, no lo que veo yo.
        """
        yo = await _create_user(user_uow, share_activity=False)
        await _publica(social_uow, yo, "mio")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert [e.source_match_id for e in feed.events] == ["mio"]

    async def test_deshacer_la_amistad_retira_sus_logros_del_feed(self, social_uow, user_uow):
        """Given un amigo con logros / When dejamos de ser amigos / Then desaparecen."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        friendship = await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1")
        use_case = _use_case(social_uow, user_uow)
        assert len((await use_case.execute(str(yo.id.value))).events) == 1

        async with social_uow:
            await social_uow.friendships.remove(friendship)

        assert (await use_case.execute(str(yo.id.value))).events == []


class TestPrivacidad:
    async def test_un_amigo_con_la_publicacion_apagada_no_aparece(self, social_uow, user_uow):
        """
        Given un amigo que apago la publicacion / When pido el feed / Then no
        sale, aunque sigamos siendo amigos y aunque le queden eventos.
        """
        yo = await _create_user(user_uow)
        callado = await _create_user(user_uow, share_activity=False)
        await _hacer_amigos(social_uow, yo, callado)
        await _publica(social_uow, callado, "match-1")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.events == []

    async def test_la_privacidad_no_recorta_la_pagina(self, social_uow, user_uow):
        """
        Given dos amigos, uno callado, con 5 logros cada uno / When pido 4 /
        Then llegan 4 del que si publica — no 2 tras filtrar los del callado.

        Es la regla de la issue: filtrar despues de paginar daria paginas de
        tamaño irregular y el cliente no sabria si quedan mas.
        """
        yo = await _create_user(user_uow)
        hablador = await _create_user(user_uow)
        callado = await _create_user(user_uow, share_activity=False)
        await _hacer_amigos(social_uow, yo, hablador)
        await _hacer_amigos(social_uow, yo, callado)
        for i in range(5):
            await _publica(social_uow, hablador, f"h-{i}", CUANDO - timedelta(days=i))
            await _publica(social_uow, callado, f"c-{i}", CUANDO - timedelta(hours=i))

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value), limit=4)

        assert len(feed.events) == 4
        assert all(e.user_id == str(hablador.id.value) for e in feed.events)


class TestPaginacion:
    async def test_pagina_sin_repetir_ni_perder(self, social_uow, user_uow):
        """Given 5 logros / When paso paginas de 2 / Then salen los 5, una vez cada uno."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        for i in range(5):
            await _publica(social_uow, amigo, f"match-{i}", CUANDO - timedelta(days=i))
        use_case = _use_case(social_uow, user_uow)

        vistos, cursor = [], None
        while True:
            pagina = await use_case.execute(str(yo.id.value), limit=2, cursor=cursor)
            vistos.extend(pagina.events)
            cursor = pagina.next_cursor
            if cursor is None:
                break

        assert len(vistos) == 5
        assert len({e.id for e in vistos}) == 5

    async def test_los_logros_de_una_misma_vuelta_no_se_pierden_al_paginar(
        self, social_uow, user_uow
    ):
        """
        Given 4 logros publicados en el mismo instante / When paso paginas de 2 /
        Then salen los 4: el cursor compara fecha e id, no solo la fecha.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        async with social_uow:
            await social_uow.activity_events.add_many(
                [
                    ActivityEvent.create(
                        user_id=amigo.id, type=t, occurred_at=CUANDO, source_match_id="match-1"
                    )
                    for t in (
                        ActivityEventType.BIRDIE,
                        ActivityEventType.EAGLE_OR_BETTER,
                        ActivityEventType.NEW_COURSE,
                        ActivityEventType.HOLE_IN_ONE,
                    )
                ]
            )
        use_case = _use_case(social_uow, user_uow)

        vistos, cursor = [], None
        while True:
            pagina = await use_case.execute(str(yo.id.value), limit=2, cursor=cursor)
            vistos.extend(pagina.events)
            cursor = pagina.next_cursor
            if cursor is None:
                break

        assert len({e.id for e in vistos}) == 4

    async def test_una_pagina_a_medias_no_da_cursor(self, social_uow, user_uow):
        """Given 1 logro / When pido 10 / Then no hay cursor: no queda nada detras."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1")

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value), limit=10)

        assert feed.next_cursor is None

    async def test_un_cursor_corrupto_devuelve_la_primera_pagina(self, social_uow, user_uow):
        """Given un cursor manipulado / When se pide / Then se empieza por arriba, sin error."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1")

        feed = await _use_case(social_uow, user_uow).execute(
            str(yo.id.value), cursor="no-soy-un-cursor"
        )

        assert len(feed.events) == 1


class TestAvisoDeNovedades:
    async def test_quien_nunca_ha_abierto_el_feed_no_ve_un_contador_enorme(
        self, social_uow, user_uow
    ):
        """
        Given un jugador que nunca abrio el feed / When lo pide / Then el aviso
        va a cero: anunciarle 200 novedades el primer dia no ayuda.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        for i in range(3):
            await _publica(social_uow, amigo, f"match-{i}", CUANDO - timedelta(days=i))

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.unseen_count == 0

    async def test_mis_propios_logros_no_cuentan_como_novedad(self, social_uow, user_uow):
        """
        Given que acabo de publicar tres logros mios / When pido el feed / Then
        el aviso sigue a cero: lo que uno acaba de hacer no es noticia para uno.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        yo.mark_feed_as_seen(CUANDO)
        async with user_uow:
            await user_uow.users.save(yo)
        for i in range(3):
            await _publica(social_uow, yo, f"mio-{i}", CUANDO + timedelta(hours=i + 1))

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert len(feed.events) == 3
        assert feed.unseen_count == 0

    async def test_cuenta_lo_publicado_despues_de_la_ultima_visita(self, social_uow, user_uow):
        """Given una visita anterior / When se publica algo nuevo / Then el aviso lo cuenta."""
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        yo.mark_feed_as_seen(CUANDO)
        async with user_uow:
            await user_uow.users.save(yo)
        await _publica(social_uow, amigo, "viejo", CUANDO - timedelta(days=1))
        await _publica(social_uow, amigo, "nuevo", CUANDO + timedelta(hours=1))

        feed = await _use_case(social_uow, user_uow).execute(str(yo.id.value))

        assert feed.unseen_count == 1


class TestCursorManipulado:
    async def test_un_cursor_con_zona_horaria_no_tumba_la_peticion(
        self, social_uow, user_uow
    ):
        """
        Given un cursor con desfase horario / When se pide el feed / Then
        responde en vez de reventar.

        El cursor viene del cliente y puede traer `+02:00` a mano. Comparar una
        fecha con zona contra las de la base de datos —que no la llevan— lanza
        TypeError y tumbaria la peticion entera.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1", CUANDO - timedelta(days=1))

        feed = await _use_case(social_uow, user_uow).execute(
            str(yo.id.value), cursor=f"{CUANDO.isoformat()}+02:00|{uuid4()}"
        )

        assert isinstance(feed.events, list)


class TestElCampo:
    """
    El nombre del campo donde ocurrio cada logro.

    El `payload` solo guarda el `golf_course_id`, asi que el nombre se resuelve
    al leer y viaja en un diccionario aparte, igual que los autores.
    """

    async def test_el_feed_trae_el_nombre_del_campo(self, social_uow, user_uow, golf_course_uow):
        """
        Given un logro en un campo / When pido el feed / Then viene como se
        llama, para no pedirlo entrada por entrada.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        campo = await _create_course(golf_course_uow, amigo.id, name="Real Club de Golf")
        await _publica(
            social_uow,
            amigo,
            "match-1",
            payload={"golf_course_id": str(campo.id.value)},
        )

        feed = await _use_case(social_uow, user_uow, golf_course_uow).execute(str(yo.id.value))

        assert feed.courses == {str(campo.id.value): "Real Club de Golf"}

    async def test_un_campo_citado_dos_veces_viaja_una_sola_vez(
        self, social_uow, user_uow, golf_course_uow
    ):
        """
        Given dos logros en el mismo campo / When pido el feed / Then el nombre
        va una vez, no uno por entrada.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        campo = await _create_course(golf_course_uow, amigo.id)
        payload = {"golf_course_id": str(campo.id.value)}
        await _publica(social_uow, amigo, "match-1", payload=payload)
        await _publica(social_uow, amigo, "match-2", payload=payload)

        feed = await _use_case(social_uow, user_uow, golf_course_uow).execute(str(yo.id.value))

        assert len(feed.events) == 2
        assert len(feed.courses) == 1

    async def test_un_campo_borrado_no_tumba_la_pagina(self, social_uow, user_uow, golf_course_uow):
        """
        Given un logro cuyo campo ya no existe / When pido el feed / Then la
        entrada sigue saliendo, solo que sin nombre.

        El logro sigue siendo cierto aunque el campo se haya borrado; perder el
        nombre no puede costar la pagina entera.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1", payload={"golf_course_id": str(uuid4())})

        feed = await _use_case(social_uow, user_uow, golf_course_uow).execute(str(yo.id.value))

        assert len(feed.events) == 1
        assert feed.courses == {}

    async def test_un_logro_sin_campo_no_pide_nombres(self, social_uow, user_uow, golf_course_uow):
        """
        Given un logro sin `golf_course_id` / When pido el feed / Then no viene
        ningun campo.
        """
        yo = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        await _hacer_amigos(social_uow, yo, amigo)
        await _publica(social_uow, amigo, "match-1")

        feed = await _use_case(social_uow, user_uow, golf_course_uow).execute(str(yo.id.value))

        assert len(feed.events) == 1
        assert feed.courses == {}
