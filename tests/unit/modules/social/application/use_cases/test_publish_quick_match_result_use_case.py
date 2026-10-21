"""
Tests de «como acabaste la partida rapida» en Actividad (BE-2, bloque D y los
extras del formato: 29, 30 y 31).

Lo ve el jugador y lo ven sus amigos (BOTH), tambien cuando queda el ultimo.
"""

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
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.publish_quick_match_result_use_case import (
    PublishQuickMatchResultUseCase,
)
from src.modules.social.application.use_cases.set_activity_sharing_use_case import (
    SetActivitySharingUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
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
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.scoring_format import ScoringFormat

pytestmark = pytest.mark.asyncio

PAR = 4
TODOS_LOS_HOYOS = range(1, 19)


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def qm_uow():
    return InMemoryQuickMatchUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def publicar(social_uow, qm_uow, golf_course_uow, user_uow):
    caso = PublishQuickMatchResultUseCase(social_uow, qm_uow, golf_course_uow, user_uow)

    async def _publicar(match) -> int:
        return await caso.execute(str(match.id.value))

    return _publicar


async def _user(user_uow, nombre: str = "Juan", share_activity: bool = True) -> User:
    user = User.create(
        first_name=nombre,
        last_name="Lopez",
        email_str=f"qmres_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _campo(golf_course_uow, creator_id):
    """Par 72: 18 hoyos de par 4, el indice igual al numero."""
    course = GolfCourse.create(
        name="El Saler",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=72.0,
                slope_rating=113,
            )
        ],
        holes=[Hole(number=i, par=PAR, stroke_index=i) for i in TODOS_LOS_HOYOS],
    )
    course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(course)
    return course


async def _partida(
    qm_uow,
    course,
    creador: User,
    tarjetas: list[dict[int, int | None]],
    otros=(),
    scoring_format: ScoringFormat | None = ScoringFormat.STABLEFORD,
    match_format: MatchFormat | None = None,
    complete: bool = True,
):
    """Una partida rapida terminada; `tarjetas[i]` es la del participante i."""
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creador.id,
        golf_course_id=course.id,
        scoring_format=scoring_format,
        match_format=match_format,
    )
    for participante in otros:
        match.add_participant(participante)
    anotador = match.participants[0].participant_id
    match.start(scorer_ids=[anotador])
    if complete:
        match.complete()

    async with qm_uow:
        await qm_uow.quick_matches.add(match)
        for participante, tarjeta in zip(match.participants, tarjetas, strict=False):
            for hoyo, golpes in tarjeta.items():
                await qm_uow.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hoyo,
                        participant_id=participante.participant_id,
                        score=golpes,
                        recorded_by_participant_id=anotador,
                    )
                )
        await qm_uow.commit()
    return match


def _tarjeta(golpes: int, **excepciones: int) -> dict[int, int | None]:
    """Los 18 hoyos con `golpes`, salvo `h3=5` y similares."""
    tarjeta: dict[int, int | None] = dict.fromkeys(TODOS_LOS_HOYOS, golpes)
    for clave, valor in excepciones.items():
        tarjeta[int(clave[1:])] = valor
    return tarjeta


async def _de(social_uow, user: User):
    async with social_uow:
        eventos = await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=50
        )
    return [e for e in eventos if e.type == ActivityEventType.QUICK_MATCH_FINISHED]


async def _uno_de(social_uow, user: User):
    (evento,) = await _de(social_uow, user)
    return evento


async def _amigos(social_uow, a: User, b: User) -> None:
    friendship = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)


async def _feed(social_uow, user_uow, viewer: User):
    return await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(viewer.id.value))


class TestStableford:
    async def test_d16_cada_uno_su_puesto_y_sus_puntos_tambien_el_ultimo(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        D16. Given un Stableford de tres a scratch / When se publica / Then cada
        uno su puesto de 3, sus puntos y sus golpes; tambien el ultimo.
        """
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        luz = await _user(user_uow, "Luz")
        course = await _campo(golf_course_uow, ana.id)
        match = await _partida(
            qm_uow,
            course,
            ana,
            [_tarjeta(4), _tarjeta(5), _tarjeta(4, h1=5)],
            otros=[QuickMatchParticipant.for_user(eva.id), QuickMatchParticipant.for_user(luz.id)],
        )

        assert await publicar(match) == 3

        de_ana = await _uno_de(social_uow, ana)
        assert de_ana.source_match_id == str(match.id.value)
        assert de_ana.payload["position"] == 1
        assert de_ana.payload["tied"] is False
        assert de_ana.payload["total_players"] == 3
        assert de_ana.payload["points"] == 36
        assert de_ana.payload["gross_strokes"] == 72
        assert de_ana.payload["scoring_format"] == "STABLEFORD"
        assert de_ana.payload["golf_course_id"] == str(course.id.value)
        assert de_ana.payload["best_gross_in_group"] is False
        de_luz = await _uno_de(social_uow, luz)
        assert (de_luz.payload["position"], de_luz.payload["points"]) == (2, 35)
        de_eva = await _uno_de(social_uow, eva)
        assert (de_eva.payload["position"], de_eva.payload["points"]) == (3, 18)
        assert de_eva.payload["gross_strokes"] == 90

    async def test_d16_tus_amigos_lo_ven(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """D16. Given mi partida publicada / When mi amigo y yo pedimos el feed / Then los dos."""
        yo = await _user(user_uow)
        amigo = await _user(user_uow)
        await _amigos(social_uow, yo, amigo)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(qm_uow, course, yo, [_tarjeta(4)])

        await publicar(match)

        tipo = ActivityEventType.QUICK_MATCH_FINISHED.value
        assert [e.type for e in (await _feed(social_uow, user_uow, amigo)).events] == [tipo]
        assert [e.type for e in (await _feed(social_uow, user_uow, yo)).events] == [tipo]

    async def test_d17_empate_a_puntos_mismo_puesto(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        D17 y 31. Given dos con 36 puntos y distintos golpes / When se publica /
        Then los dos 1.º empatados, y el tercero 3.º: no desempatan los golpes.
        """
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        luz = await _user(user_uow, "Luz")
        course = await _campo(golf_course_uow, ana.id)
        # Eva: dos birdies (+2 puntos) y un triple bogey (-2): 36 con 73 golpes
        match = await _partida(
            qm_uow,
            course,
            ana,
            [_tarjeta(4), _tarjeta(4, h1=3, h2=3, h3=7), _tarjeta(5)],
            otros=[QuickMatchParticipant.for_user(eva.id), QuickMatchParticipant.for_user(luz.id)],
        )

        await publicar(match)

        de_ana = await _uno_de(social_uow, ana)
        de_eva = await _uno_de(social_uow, eva)
        assert de_ana.payload["points"] == de_eva.payload["points"] == 36
        assert de_eva.payload["gross_strokes"] == 73
        assert (de_ana.payload["position"], de_ana.payload["tied"]) == (1, True)
        assert (de_eva.payload["position"], de_eva.payload["tied"]) == (1, True)
        de_luz = await _uno_de(social_uow, luz)
        assert (de_luz.payload["position"], de_luz.payload["tied"]) == (3, False)

    async def test_d18_jugando_solo_hay_puntos_sin_puesto(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """D18. Given una partida de uno / When se publica / Then sus puntos, sin puesto."""
        yo = await _user(user_uow)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(qm_uow, course, yo, [_tarjeta(4)])

        await publicar(match)

        evento = await _uno_de(social_uow, yo)
        assert evento.payload["points"] == 36
        assert evento.payload["position"] is None
        assert evento.payload["total_players"] == 1
        assert evento.payload["best_gross_in_group"] is False

    async def test_30_mejor_bruto_del_grupo_si_no_quedo_primero(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        30. Given Eva con 36 de hándicap gana a puntos y Ana hace menos golpes /
        When se publica / Then Ana 2.ª con la etiqueta de mejor bruto; Eva sin ella.
        """
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        course = await _campo(golf_course_uow, ana.id)
        match = await _partida(
            qm_uow,
            course,
            ana,
            [_tarjeta(4, h1=5), _tarjeta(5)],
            otros=[QuickMatchParticipant.for_user(eva.id).with_handicap(36)],
        )

        await publicar(match)

        de_ana = await _uno_de(social_uow, ana)
        de_eva = await _uno_de(social_uow, eva)
        assert de_eva.payload["position"] == 1
        assert de_ana.payload["position"] == 2
        assert de_ana.payload["gross_strokes"] == 73
        assert de_ana.payload["best_gross_in_group"] is True
        assert de_eva.payload["best_gross_in_group"] is False


class TestMedal:
    async def test_29_medal_lleva_neto_y_bruto(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        29. Given un Medal a scratch / When se publica / Then el neto, el bruto
        y el resultado contra el par; y gana quien menos golpes hace.
        """
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        course = await _campo(golf_course_uow, ana.id)
        match = await _partida(
            qm_uow,
            course,
            ana,
            [_tarjeta(4, h1=5), _tarjeta(4, h1=3)],
            otros=[QuickMatchParticipant.for_user(eva.id)],
            scoring_format=ScoringFormat.MEDAL,
        )

        await publicar(match)

        de_ana = await _uno_de(social_uow, ana)
        de_eva = await _uno_de(social_uow, eva)
        assert de_ana.payload["scoring_format"] == "MEDAL"
        assert de_ana.payload["net_strokes"] == 73
        assert de_ana.payload["gross_strokes"] == 73
        assert de_ana.payload["to_par"] == 1
        assert "points" not in de_ana.payload
        assert (de_eva.payload["position"], de_ana.payload["position"]) == (1, 2)
        assert de_eva.payload["to_par"] == -1

    async def test_29_el_neto_descuenta_los_golpes_recibidos(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """29. Given un Medal con 36 de hándicap / When se publica / Then neto menor que bruto."""
        yo = await _user(user_uow)
        yo.update_handicap(36)
        async with user_uow:
            await user_uow.users.save(yo)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(
            qm_uow,
            course,
            yo,
            [_tarjeta(5), _tarjeta(5)],
            otros=[QuickMatchParticipant.for_guest("Seve", "Ballesteros", handicap=0)],
            scoring_format=ScoringFormat.MEDAL,
        )

        await publicar(match)

        evento = await _uno_de(social_uow, yo)
        assert evento.payload["gross_strokes"] == 90
        assert evento.payload["net_strokes"] < 90
        assert evento.payload["to_par"] == evento.payload["net_strokes"] - 72
        assert evento.payload["position"] == 1

    async def test_31_empate_en_medal(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """31. Given dos Medal con el mismo neto / When se publica / Then 1.º empatados."""
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        course = await _campo(golf_course_uow, ana.id)
        match = await _partida(
            qm_uow,
            course,
            ana,
            [_tarjeta(4), _tarjeta(4, h1=5, h2=3)],
            otros=[QuickMatchParticipant.for_user(eva.id)],
            scoring_format=ScoringFormat.MEDAL,
        )

        await publicar(match)

        for user in (ana, eva):
            evento = await _uno_de(social_uow, user)
            assert (evento.payload["position"], evento.payload["tied"]) == (1, True)


class TestMatchPlay:
    async def test_d19_match_play_ganaste_3_y_2(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        D19. Given un individual que Ana gana 3&2 / When se publica / Then Ana
        WON 3&2 contra Eva, Eva LOST, y el amigo de Ana lo ve.
        """
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        amigo = await _user(user_uow, "Amigo")
        await _amigos(social_uow, ana, amigo)
        course = await _campo(golf_course_uow, ana.id)
        dieciseis = dict.fromkeys(range(1, 17), 4)
        match = await _partida(
            qm_uow,
            course,
            ana,
            [{**dieciseis, 1: 3, 2: 3, 3: 3}, dieciseis],
            otros=[QuickMatchParticipant.for_user(eva.id)],
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
        )

        await publicar(match)

        de_ana = await _uno_de(social_uow, ana)
        de_eva = await _uno_de(social_uow, eva)
        assert (de_ana.payload["outcome"], de_ana.payload["score"]) == ("WON", "3&2")
        assert (de_eva.payload["outcome"], de_eva.payload["score"]) == ("LOST", "3&2")
        assert de_ana.payload["match_format"] == "SINGLES"
        assert de_ana.payload["opponents"] == [{"user_id": str(eva.id.value), "name": None}]
        assert "position" not in de_ana.payload
        feed = (await _feed(social_uow, user_uow, amigo)).events
        assert [e.payload["outcome"] for e in feed] == ["WON"]

    async def test_d20_el_invitado_no_tiene_aviso_y_sale_por_su_nombre(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        D20. Given un individual contra un invitado / When se publica / Then un
        aviso, el mio, con el invitado por el nombre de la partida.
        """
        yo = await _user(user_uow)
        course = await _campo(golf_course_uow, yo.id)
        dieciocho = _tarjeta(4)
        match = await _partida(
            qm_uow,
            course,
            yo,
            [dieciocho, dieciocho],
            otros=[QuickMatchParticipant.for_guest("Seve", "Ballesteros")],
            scoring_format=None,
            match_format=MatchFormat.SINGLES,
        )

        assert await publicar(match) == 1

        evento = await _uno_de(social_uow, yo)
        assert (evento.payload["outcome"], evento.payload["score"]) == ("HALVED", "AS")
        assert evento.payload["opponents"] == [{"user_id": None, "name": "Seve Ballesteros"}]

    async def test_d20_el_invitado_cuenta_en_la_clasificacion(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """D20. Given un Stableford con un invitado que gana / When se publica / Then soy 2.º de 2."""
        yo = await _user(user_uow)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(
            qm_uow,
            course,
            yo,
            [_tarjeta(5), _tarjeta(4)],
            otros=[QuickMatchParticipant.for_guest("Seve", "Ballesteros")],
        )

        assert await publicar(match) == 1

        evento = await _uno_de(social_uow, yo)
        assert (evento.payload["position"], evento.payload["total_players"]) == (2, 2)


class TestRobustez:
    async def test_d21_con_la_publicacion_apagada_lo_ves_tu_y_no_tus_amigos(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        D21. Given la publicacion apagada / When se publica y luego la enciendo /
        Then yo lo veo; mi amigo no, ni entonces ni despues.
        """
        yo = await _user(user_uow, share_activity=False)
        amigo = await _user(user_uow)
        await _amigos(social_uow, yo, amigo)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(qm_uow, course, yo, [_tarjeta(4)])

        await publicar(match)
        assert len((await _feed(social_uow, user_uow, yo)).events) == 1
        assert (await _feed(social_uow, user_uow, amigo)).events == []

        await SetActivitySharingUseCase(user_uow, social_uow).execute(
            str(yo.id.value), enabled=True
        )
        assert (await _feed(social_uow, user_uow, amigo)).events == []

    async def test_publicar_dos_veces_no_duplica(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        yo = await _user(user_uow)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(qm_uow, course, yo, [_tarjeta(4)])

        await publicar(match)
        await publicar(match)

        assert len(await _de(social_uow, yo)) == 1

    async def test_una_partida_sin_terminar_no_se_publica(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        yo = await _user(user_uow)
        course = await _campo(golf_course_uow, yo.id)
        match = await _partida(qm_uow, course, yo, [_tarjeta(4)], complete=False)

        assert await publicar(match) == 0

    async def test_quien_no_anoto_nada_no_tiene_aviso_ni_cuenta(
        self, publicar, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given un jugador sin ningun hoyo / When se publica / Then sin aviso y fuera del total."""
        ana = await _user(user_uow, "Ana")
        eva = await _user(user_uow, "Eva")
        course = await _campo(golf_course_uow, ana.id)
        match = await _partida(
            qm_uow, course, ana, [_tarjeta(4), {}], otros=[QuickMatchParticipant.for_user(eva.id)]
        )

        assert await publicar(match) == 1

        evento = await _uno_de(social_uow, ana)
        assert evento.payload["total_players"] == 1
        assert evento.payload["position"] is None
        assert await _de(social_uow, eva) == []
