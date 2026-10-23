"""
La actividad de un jugador trae a sus autores y sus campos, como el feed.

Revision de punta a punta (22 oct): `GET /users/{id}/activity` devolvia
`authors: {}` y `courses: {}`, y en el perfil de un amigo el cliente pintaba
al dueño y a sus rivales como «un jugador» y sin campo. Son las mismas
tarjetas que el feed, asi que se resuelven igual y con la misma privacidad.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
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
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

CUANDO = datetime(2026, 8, 10, 12, 0)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


async def _user(user_uow, nombre: str = "Ana") -> User:
    user = User.create(
        first_name=nombre,
        last_name="Garcia",
        email_str=f"ref_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amistad(social_uow, a: User, b: User, estado: str = "amigos") -> None:
    amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    if estado == "amigos":
        amistad.accept()
    else:
        amistad.block(a.id)
    async with social_uow:
        await social_uow.friendships.add(amistad)


async def _campo(golf_course_uow, creador: User, nombre: str) -> str:
    campo = GolfCourse.create(
        name=nombre,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creador.id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
            Tee(
                color=TeeColor.WHITE,
                gender=Gender.MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            ),
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    campo.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(campo)
    return str(campo.id.value)


async def _resultado(social_uow, autor: User, payload: dict) -> None:
    async with social_uow:
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=autor.id,
                    type=ActivityEventType.QUICK_MATCH_FINISHED,
                    occurred_at=CUANDO,
                    source_match_id=f"partida-{uuid4().hex[:6]}",
                    published_at=CUANDO,
                    payload=payload,
                )
            ]
        )


def _con_cuenta(user: User) -> dict:
    return {"user_id": str(user.id.value), "name": None}


async def _actividad(social_uow, user_uow, golf_course_uow, viewer: User, target: User):
    return await GetPlayerActivityUseCase(social_uow, user_uow, golf_course_uow).execute(
        str(viewer.id.value), str(target.id.value)
    )


class _Contador:
    """Envuelve un repositorio y cuenta cada llamada a los metodos indicados."""

    def __init__(self, repo, *metodos: str):
        self._repo = repo
        self.llamadas = dict.fromkeys(metodos, 0)

    def __getattr__(self, name):
        atributo = getattr(self._repo, name)
        if name not in self.llamadas:
            return atributo

        async def contado(*args, **kwargs):
            self.llamadas[name] += 1
            return await atributo(*args, **kwargs)

        return contado


class TestAutoresYCampos:
    async def test_el_perfil_de_un_amigo_trae_a_su_dueno_rivales_y_campo(
        self, social_uow, user_uow, golf_course_uow
    ):
        """
        Given la partida de mi amigo contra Eva con Luz de compañera, en un
        campo / When abro su actividad / Then vienen los tres con nombre y el
        campo con el suyo.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        eva = await _user(user_uow, "Eva")
        luz = await _user(user_uow, "Luz")
        await _amistad(social_uow, yo, amigo)
        campo = await _campo(golf_course_uow, amigo, "Real Club de Golf")
        await _resultado(
            social_uow,
            amigo,
            {
                "opponents": [_con_cuenta(eva)],
                "partners": [_con_cuenta(luz)],
                "golf_course_id": campo,
            },
        )

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        assert set(actividad.authors) == {str(u.id.value) for u in (amigo, eva, luz)}
        assert actividad.authors[str(amigo.id.value)].first_name == "Amigo"
        assert actividad.courses == {campo: "Real Club de Golf"}

    async def test_mi_propia_actividad_me_trae_a_mi_y_a_los_de_torneo(
        self, social_uow, user_uow, golf_course_uow
    ):
        """Given mi resultado de torneo / When abro mi actividad / Then salgo yo y mi rival."""
        yo = await _user(user_uow)
        eva = await _user(user_uow, "Eva")
        await _resultado(social_uow, yo, {"opponent_ids": [str(eva.id.value)]})

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, yo)

        assert set(actividad.authors) == {str(yo.id.value), str(eva.id.value)}

    async def test_igual_que_el_feed(self, social_uow, user_uow, golf_course_uow):
        """
        Given una partida de mi amigo / When la veo en el feed y en su perfil /
        Then autores y campos son los mismos: una sola regla para las dos.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        eva = await _user(user_uow, "Eva")
        await _amistad(social_uow, yo, amigo)
        campo = await _campo(golf_course_uow, amigo, "El Prat")
        await _resultado(
            social_uow, amigo, {"opponents": [_con_cuenta(eva)], "golf_course_id": campo}
        )

        feed = await GetFriendsFeedUseCase(social_uow, user_uow, golf_course_uow).execute(
            str(yo.id.value)
        )
        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        # El feed me trae tambien a mi (soy autor de la pagina, aunque no de esta tarjeta)
        assert set(actividad.authors) <= set(feed.authors)
        assert set(actividad.authors) == {str(amigo.id.value), str(eva.id.value)}
        assert actividad.courses == feed.courses == {campo: "El Prat"}


class TestPrivacidadDeLosNombrados:
    @pytest.mark.parametrize("quien_bloquea", ["yo", "ella"])
    async def test_un_bloqueado_entre_quien_mira_y_el_nombrado_no_viene(
        self, social_uow, user_uow, golf_course_uow, quien_bloquea
    ):
        """
        Given la partida de mi amigo contra Eva, con un bloqueo entre Eva y yo /
        When abro su actividad / Then Eva no viene («un jugador»), mi amigo si.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        eva = await _user(user_uow, "Eva")
        await _amistad(social_uow, yo, amigo)
        if quien_bloquea == "yo":
            await _amistad(social_uow, yo, eva, "bloqueo")
        else:
            await _amistad(social_uow, eva, yo, "bloqueo")
        await _resultado(social_uow, amigo, {"opponents": [_con_cuenta(eva)]})

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        assert set(actividad.authors) == {str(amigo.id.value)}

    async def test_el_bloqueo_del_dueno_con_otro_no_me_afecta(
        self, social_uow, user_uow, golf_course_uow
    ):
        """El bloqueo se mira contra quien MIRA, no contra el dueño del perfil."""
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        eva = await _user(user_uow, "Eva")
        await _amistad(social_uow, yo, amigo)
        await _amistad(social_uow, amigo, eva, "bloqueo")
        await _resultado(social_uow, amigo, {"opponents": [_con_cuenta(eva)]})

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        assert str(eva.id.value) in actividad.authors

    async def test_una_cuenta_desactivada_no_viene(self, social_uow, user_uow, golf_course_uow):
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        eva = await _user(user_uow, "Eva")
        eva.deactivate(str(uuid4()))
        async with user_uow:
            await user_uow.users.save(eva)
        await _amistad(social_uow, yo, amigo)
        await _resultado(social_uow, amigo, {"opponents": [_con_cuenta(eva)]})

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        assert set(actividad.authors) == {str(amigo.id.value)}

    async def test_el_invitado_no_filtra_su_nombre(self, social_uow, user_uow, golf_course_uow):
        """
        Given la partida de mi amigo contra un invitado / When abro su actividad
        / Then ni el payload ni los autores llevan su nombre.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        await _amistad(social_uow, yo, amigo)
        await _resultado(
            social_uow, amigo, {"opponents": [{"user_id": None, "name": "Seve Ballesteros"}]}
        )

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        (evento,) = actividad.events
        assert evento.payload["opponents"] == [{"user_id": None, "name": None}]
        assert set(actividad.authors) == {str(amigo.id.value)}
        assert "Seve" not in repr(actividad.authors)

    async def test_ids_ilegibles_no_rompen(self, social_uow, user_uow, golf_course_uow):
        """
        Given un payload con un rival y un campo que no son UUID / When abro la
        actividad / Then sale la entrada, con su dueño y sin campo.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        await _amistad(social_uow, yo, amigo)
        await _resultado(
            social_uow,
            amigo,
            {
                "opponent_ids": ["no-es-un-uuid", 7],
                "opponents": [{"user_id": "tampoco"}],
                "golf_course_id": "not-a-uuid",
            },
        )

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        assert len(actividad.events) == 1
        assert set(actividad.authors) == {str(amigo.id.value)}
        assert actividad.courses == {}


class TestPorLotes:
    async def test_usuarios_y_campos_en_lecturas_fijas(self, social_uow, user_uow, golf_course_uow):
        """
        Given cinco partidas de mi amigo con rivales distintos en tres campos /
        When abro su actividad / Then los nombrados se leen en una lectura por
        lote, y los campos en otra: ninguna de uno en uno.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow, "Amigo")
        await _amistad(social_uow, yo, amigo)
        campos = [await _campo(golf_course_uow, amigo, f"Campo {i}") for i in range(3)]
        for i in range(5):
            rival = await _user(user_uow, f"Rival{i}")
            await _resultado(
                social_uow,
                amigo,
                {"opponents": [_con_cuenta(rival)], "golf_course_id": campos[i % 3]},
            )
        usuarios = _Contador(user_uow.users, "find_by_id", "find_by_ids")
        user_uow._users = usuarios
        repo_campos = _Contador(golf_course_uow.golf_courses, "find_by_id", "find_names_by_ids")
        golf_course_uow._golf_courses = repo_campos

        actividad = await _actividad(social_uow, user_uow, golf_course_uow, yo, amigo)

        assert len(actividad.authors) == 6
        assert len(actividad.courses) == 3
        # Una lectura del dueño del perfil (la de siempre) y una por lote
        assert usuarios.llamadas == {"find_by_id": 1, "find_by_ids": 1}
        assert repo_campos.llamadas == {"find_by_id": 0, "find_names_by_ids": 1}

    async def test_el_feed_lee_los_campos_en_una_sola_consulta(
        self, social_uow, user_uow, golf_course_uow
    ):
        """La pieza es la misma: el feed tampoco lee los campos de uno en uno."""
        yo = await _user(user_uow)
        campos = [await _campo(golf_course_uow, yo, f"Campo {i}") for i in range(3)]
        for campo in campos:
            await _resultado(social_uow, yo, {"golf_course_id": campo})
        repo_campos = _Contador(golf_course_uow.golf_courses, "find_by_id", "find_names_by_ids")
        golf_course_uow._golf_courses = repo_campos

        feed = await GetFriendsFeedUseCase(social_uow, user_uow, golf_course_uow).execute(
            str(yo.id.value)
        )

        assert len(feed.courses) == 3
        assert repo_campos.llamadas == {"find_by_id": 0, "find_names_by_ids": 1}
