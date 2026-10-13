"""
Tests para CreateAndStartQuickMatchUseCase (FE #848).

El asistente de partida rápida ya no crea nada hasta «Confirmar e iniciar»:
una sola petición crea la partida con todos sus jugadores, la inicia y fija
los hándicaps. Tabla aprobada el 13 oct 2026:

    #   caso                                        | qué pasa
    ----|---------------------------------------------|----------------------------------
    1   todo bien (individual, parejas, libre)      | IN_PROGRESS, anotadores y hándicaps
        |                                             | congelados
    2   algo falla                                  | no se guarda NADA
    3   hándicaps                                   | el cambiado manda; si no, el del
        |                                             | perfil; el invitado, el suyo
    4   campo inexistente / no aprobado / barra     | 404 / 422 / 422
    5   amigo inexistente / no amigo / repetido o   | 404 / 403 / 409
        | el propio creador                           |
    6   sobran jugadores, equipo lleno o mal, o     | 422
        | plantilla incompleta                        |
    7   anotadores sin el creador, repetidos, un    | 422
        | invitado o alguien que no juega             |

Y lo que añadió la revisión (13 oct):

    8   el orden de los jugadores                   | el de la lista: el que eligió
    9   el mismo id otra vez, del mismo creador     | la partida que ya existe, sin crear
        |                                             | otra (reintento seguro)
    9b  el mismo id, de otro creador                | QuickMatchIdTakenError (409)
    10  invitado con el nombre en blanco            | InvalidParticipantError (422)
"""

from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.dto.quick_match_dto import (
    CreateAndStartQuickMatchRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    FriendUserNotFoundError,
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
    InvalidParticipantError,
    InvalidTeeSelectionError,
    NotFriendsError,
    QuickMatchIdTakenError,
)
from src.modules.quick_match.application.use_cases.create_and_start_quick_match_use_case import (
    CreateAndStartQuickMatchUseCase,
)
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    DuplicateParticipantViolation,
    IncompleteRosterViolation,
    InvalidScorerConfigurationViolation,
    InvalidTeamAssignmentViolation,
    QuickMatchFullViolation,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.quick_match.conftest import (
    create_accepted_friendship,
    create_golf_course,
    create_user,
    unique_email,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def use_case(qm_uow, golf_course_uow, social_uow, user_uow):
    return CreateAndStartQuickMatchUseCase(qm_uow, golf_course_uow, social_uow, user_uow)


async def _jugadores(user_uow, social_uow, golf_course_uow, amigos=1):
    creator = await create_user(user_uow, unique_email("creator"), handicap=12.0)
    friends = []
    for i in range(amigos):
        friend = await create_user(user_uow, unique_email(f"friend{i}"), handicap=20.0 + i)
        await create_accepted_friendship(social_uow, creator.id, friend.id)
        friends.append(friend)
    course = await create_golf_course(golf_course_uow, creator.id)
    return creator, friends, course


def _peticion(creator, course, friends=(), guests=(), **extra):
    datos = {
        "quick_match_id": uuid4(),
        "creator_id": creator.id.value,
        "golf_course_id": course.id.value,
        "match_format": "SINGLES",
        "creator_tee_color": "WHITE",
        "creator_tee_gender": "MALE",
        "scorer_user_ids": [creator.id.value],
        "participants": [*friends, *guests],
    }
    datos.update(extra)
    return CreateAndStartQuickMatchRequestDTO(**datos)


def _amigo(friend, **extra):
    return {
        "kind": "FRIEND",
        "friend_user_id": friend.id.value,
        "tee_color": "YELLOW",
        "tee_gender": "MALE",
        **extra,
    }


def _invitado(**extra):
    return {
        "kind": "GUEST",
        "first_name": "Ana",
        "last_name": "Pérez",
        "handicap": 18.4,
        "tee_color": "YELLOW",
        "tee_gender": "MALE",
        **extra,
    }


async def _inicia(use_case, peticion):
    resultado = await use_case.execute(peticion)
    assert resultado.created is True
    return resultado.quick_match


async def _guardadas(qm_uow, creator):
    async with qm_uow:
        return await qm_uow.quick_matches.list_for_user(creator.id)


class TestTodoBien:
    async def test_1_individual_en_juego_con_sus_anotadores(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        r = await _inicia(
            use_case,
            _peticion(
                creator,
                course,
                friends=[_amigo(friend)],
                scorer_user_ids=[creator.id.value, friend.id.value],
            ),
        )

        assert r.status == "IN_PROGRESS"
        assert [p.user_id for p in r.participants] == [creator.id.value, friend.id.value]
        assert set(r.scorer_ids) == {creator.id.value, friend.id.value}
        assert [p.tee_color for p in r.participants] == ["WHITE", "YELLOW"]
        assert len(await _guardadas(qm_uow, creator)) == 1

    async def test_1b_parejas_con_equipos_e_invitados(
        self, use_case, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        r = await _inicia(
            use_case,
            _peticion(
                creator,
                course,
                match_format="FOURBALL",
                friends=[_amigo(friend, team="A")],
                guests=[_invitado(team="B"), _invitado(first_name="Bea", team="B")],
            ),
        )

        assert r.status == "IN_PROGRESS"
        assert [p.team for p in r.participants] == ["A", "A", "B", "B"]
        assert [p.is_guest for p in r.participants] == [False, False, True, True]

    async def test_1c_juego_libre_solo(self, use_case, user_uow, social_uow, golf_course_uow):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        r = await _inicia(
            use_case, _peticion(creator, course, match_format=None, scoring_format="STABLEFORD")
        )

        assert r.status == "IN_PROGRESS"
        assert len(r.participants) == 1


class TestHandicaps:
    async def test_3_el_cambiado_manda_y_si_no_el_del_perfil(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, friends, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=2)

        await use_case.execute(
            _peticion(
                creator,
                course,
                match_format=None,
                scoring_format="MEDAL",
                creator_handicap=9.5,
                friends=[_amigo(friends[0], handicap=30.0), _amigo(friends[1])],
                guests=[_invitado()],
            )
        )

        (guardada,) = await _guardadas(qm_uow, creator)
        congelados = [p.starting_handicap for p in guardada.participants]
        assert congelados == [9.5, 30.0, 21.0, 18.4]

    async def test_3b_invitado_sin_handicap_juega_sin_el(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        await use_case.execute(_peticion(creator, course, guests=[_invitado(handicap=None)]))

        (guardada,) = await _guardadas(qm_uow, creator)
        assert guardada.participants[1].starting_handicap is None


class TestElCampo:
    async def test_4_campo_inexistente(self, use_case, user_uow, social_uow, golf_course_uow):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)
        peticion = _peticion(creator, course, golf_course_id=uuid4())

        with pytest.raises(GolfCourseNotFoundError):
            await use_case.execute(peticion)

    async def test_4b_campo_sin_aprobar(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, _, _ = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)
        pendiente = GolfCourse.create(
            name="Pendiente",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator.id,
            tees=[
                Tee(
                    color=TeeColor.WHITE,
                    gender=Gender.MALE,
                    identifier="White",
                    course_rating=72.0,
                    slope_rating=130,
                )
            ],
            holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
        )
        async with golf_course_uow:
            await golf_course_uow.golf_courses.save(pendiente)

        with pytest.raises(GolfCourseNotApprovedError):
            await use_case.execute(_peticion(creator, pendiente))
        assert await _guardadas(qm_uow, creator) == []

    @pytest.mark.parametrize("quien", ["creador", "amigo", "invitado"])
    async def test_4c_una_barra_que_el_campo_no_tiene(
        self, quien, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)
        mala = {"tee_color": "RED", "tee_gender": "FEMALE"}
        extra = {
            "creador": {
                "creator_tee_color": "RED",
                "creator_tee_gender": "FEMALE",
                "friends": [_amigo(friend)],
            },
            "amigo": {"friends": [_amigo(friend, **mala)]},
            "invitado": {"guests": [_invitado(**mala)]},
        }[quien]

        with pytest.raises(InvalidTeeSelectionError):
            await use_case.execute(_peticion(creator, course, **extra))
        assert await _guardadas(qm_uow, creator) == []


class TestLosAmigos:
    async def test_5_amigo_inexistente(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)
        fantasma = {
            "kind": "FRIEND",
            "friend_user_id": uuid4(),
            "tee_color": "YELLOW",
            "tee_gender": "MALE",
        }

        with pytest.raises(FriendUserNotFoundError):
            await use_case.execute(_peticion(creator, course, friends=[fantasma]))
        assert await _guardadas(qm_uow, creator) == []

    async def test_5b_no_es_amigo(self, use_case, qm_uow, user_uow, social_uow, golf_course_uow):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)
        extrano = await create_user(user_uow, unique_email("stranger"))

        with pytest.raises(NotFriendsError):
            await use_case.execute(_peticion(creator, course, friends=[_amigo(extrano)]))
        assert await _guardadas(qm_uow, creator) == []

    async def test_5c_repetido(self, use_case, qm_uow, user_uow, social_uow, golf_course_uow):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        with pytest.raises(DuplicateParticipantViolation):
            await use_case.execute(
                _peticion(
                    creator,
                    course,
                    match_format=None,
                    scoring_format="MEDAL",
                    friends=[_amigo(friend), _amigo(friend)],
                )
            )
        assert await _guardadas(qm_uow, creator) == []

    async def test_5d_el_propio_creador(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        with pytest.raises(DuplicateParticipantViolation):
            await use_case.execute(_peticion(creator, course, friends=[_amigo(creator)]))
        assert await _guardadas(qm_uow, creator) == []


class TestLaPlantilla:
    async def test_6_sobran_jugadores(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        with pytest.raises(QuickMatchFullViolation):
            await use_case.execute(
                _peticion(creator, course, friends=[_amigo(friend)], guests=[_invitado()])
            )
        assert await _guardadas(qm_uow, creator) == []

    async def test_6b_equipo_lleno(self, use_case, user_uow, social_uow, golf_course_uow):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        with pytest.raises(QuickMatchFullViolation, match="Team A"):
            await use_case.execute(
                _peticion(
                    creator,
                    course,
                    match_format="FOURBALL",
                    friends=[_amigo(friend, team="A")],
                    guests=[_invitado(team="A"), _invitado(first_name="Bea", team="B")],
                )
            )

    async def test_6c_sin_equipo_en_parejas(self, use_case, user_uow, social_uow, golf_course_uow):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        with pytest.raises(InvalidTeamAssignmentViolation):
            await use_case.execute(
                _peticion(creator, course, match_format="FOURSOMES", friends=[_amigo(friend)])
            )

    async def test_6d_plantilla_incompleta(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        with pytest.raises(IncompleteRosterViolation):
            await use_case.execute(_peticion(creator, course))
        assert await _guardadas(qm_uow, creator) == []


class TestLosAnotadores:
    async def test_7_sin_el_creador(self, use_case, qm_uow, user_uow, social_uow, golf_course_uow):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        with pytest.raises(InvalidScorerConfigurationViolation):
            await use_case.execute(
                _peticion(
                    creator,
                    course,
                    friends=[_amigo(friend)],
                    scorer_user_ids=[friend.id.value],
                )
            )
        assert await _guardadas(qm_uow, creator) == []

    async def test_7b_alguien_que_no_juega(self, use_case, user_uow, social_uow, golf_course_uow):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        with pytest.raises(InvalidScorerConfigurationViolation):
            await use_case.execute(
                _peticion(
                    creator,
                    course,
                    guests=[_invitado()],
                    scorer_user_ids=[creator.id.value, friend.id.value],
                )
            )


class TestLoQueAnadioLaRevision:
    async def test_8_el_orden_es_el_de_la_lista(
        self, use_case, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)

        r = await _inicia(
            use_case,
            _peticion(
                creator,
                course,
                match_format=None,
                scoring_format="MEDAL",
                participants=[_invitado(), _amigo(friend)],
            ),
        )

        assert [p.is_guest for p in r.participants] == [False, True, False]
        assert r.participants[2].user_id == friend.id.value

    async def test_9_el_mismo_id_del_mismo_creador_devuelve_la_que_hay(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)
        peticion = _peticion(creator, course, friends=[_amigo(friend)])

        primera = await use_case.execute(peticion)
        segunda = await use_case.execute(peticion)

        assert primera.created is True
        assert segunda.created is False
        assert segunda.quick_match.id == primera.quick_match.id
        assert segunda.quick_match.status == "IN_PROGRESS"
        assert len(await _guardadas(qm_uow, creator)) == 1

    async def test_9b_el_mismo_id_de_otro_creador(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, (friend,), course = await _jugadores(user_uow, social_uow, golf_course_uow)
        peticion = _peticion(creator, course, friends=[_amigo(friend)])
        await use_case.execute(peticion)
        otro, _, otro_campo = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        with pytest.raises(QuickMatchIdTakenError):
            await use_case.execute(
                _peticion(
                    otro,
                    otro_campo,
                    match_format=None,
                    scoring_format="MEDAL",
                    quick_match_id=peticion.quick_match_id,
                )
            )
        assert await _guardadas(qm_uow, otro) == []

    async def test_10_invitado_con_el_nombre_en_blanco(
        self, use_case, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        with pytest.raises(InvalidParticipantError):
            await use_case.execute(_peticion(creator, course, guests=[_invitado(first_name="   ")]))
        assert await _guardadas(qm_uow, creator) == []

    async def test_7c_anotadores_repetidos_no_pasan_del_dto(
        self, user_uow, social_uow, golf_course_uow
    ):
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        with pytest.raises(ValueError, match="duplicates"):
            _peticion(creator, course, scorer_user_ids=[creator.id.value, creator.id.value])

    async def test_7d_un_invitado_no_anota(self, use_case, user_uow, social_uow, golf_course_uow):
        """El invitado no tiene UserId: un id que no es de un registrado no anota."""
        creator, _, course = await _jugadores(user_uow, social_uow, golf_course_uow, amigos=0)

        with pytest.raises(InvalidScorerConfigurationViolation):
            await use_case.execute(
                _peticion(
                    creator,
                    course,
                    guests=[_invitado()],
                    scorer_user_ids=[creator.id.value, uuid4()],
                )
            )
