"""
Tests de la publicacion de logros en el feed (BE #175).

Lo que mas importa aqui: **se publican logros, no actividad**, y solo de vueltas
que cuentan. Una tarjeta incompleta no llega al feed, igual que no llega a las
estadisticas (BE #173/#174), y un jugador que apago la publicacion no aparece.
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
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
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

PAR = 4


class _DifferentialsStub(PlayerDifferentialsInterface):
    """El mejor diferencial de cada jugador, fijado por el test."""

    def __init__(self, por_jugador: dict | None = None):
        self._por_jugador = por_jugador or {}

    async def best_differential(self, user_id):
        return self._por_jugador.get(str(user_id.value))


class _CourseHistoryFake(PlayerCourseHistoryInterface):
    """
    Historial de campos en memoria.

    Recuerda cada vuelta que se le pregunta, que es lo que hace el adaptador de
    verdad al consultar partidas rapidas y torneos: la segunda vez que un
    jugador pisa un campo, ya no lo estrena.
    """

    def __init__(self):
        self._vueltas: set = set()

    def registra(self, user_id, golf_course_id: str, match_id: str) -> None:
        self._vueltas.add((str(user_id.value), golf_course_id, match_id))

    async def has_played_course_before(
        self, user_id, golf_course_id: str, excluding_match_id: str
    ) -> bool:
        return any(
            usuario == str(user_id.value)
            and campo == golf_course_id
            and partida != excluding_match_id
            for usuario, campo, partida in self._vueltas
        )


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


async def _create_user(user_uow, share_activity: bool = True) -> User:
    user = User.create(
        first_name="Test",
        last_name="User",
        email_str=f"feed_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _create_course(golf_course_uow, creator_id, name: str = "Test Golf Club"):
    """Campo de par 72: 18 hoyos de par 4."""
    course = GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
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
        holes=[Hole(number=i, par=PAR, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(course)
    return course


async def _played_match(
    qm_uow,
    course,
    user,
    *,
    scores_by_hole: dict | None = None,
    others=(),
    complete: bool = True,
):
    """Una partida rapida terminada con la vuelta anotada."""
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=user.id,
        golf_course_id=course.id,
        scoring_format=ScoringFormat.MEDAL,
        creator_tee_color=TeeColor.YELLOW,
        creator_tee_gender=Gender.MALE,
    )
    for participant in others:
        match.add_participant(participant)

    creator_participant_id = match.participants[0].participant_id
    match.start(scorer_ids=[creator_participant_id])
    if complete:
        match.complete()

    tarjeta = scores_by_hole or dict.fromkeys(range(1, 19), PAR)

    async with qm_uow:
        await qm_uow.quick_matches.add(match)
        for participant in match.participants:
            for hole_number, strokes in tarjeta.items():
                await qm_uow.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hole_number,
                        participant_id=participant.participant_id,
                        score=strokes,
                        recorded_by_participant_id=creator_participant_id,
                    )
                )
        await qm_uow.commit()

    return match


def _use_case(social_uow, qm_uow, golf_course_uow, user_uow, differentials=None, history=None):
    return PublishRoundAchievementsUseCase(
        social_uow=social_uow,
        quick_match_uow=qm_uow,
        golf_course_uow=golf_course_uow,
        user_uow=user_uow,
        differentials=differentials or _DifferentialsStub(),
        history=history or _CourseHistoryFake(),
    )


async def _feed_de(social_uow, user):
    async with social_uow:
        return await social_uow.activity_events.find_for_users([user.id], limit=50)


class TestQueSePublica:
    async def test_agrupa_los_birdies_de_la_vuelta_en_una_sola_entrada(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given una vuelta con tres birdies / When se publica / Then hay una
        entrada que dice tres, no tres entradas empujandose en el feed.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        tarjeta = dict.fromkeys(range(1, 19), PAR)
        for hoyo in (1, 5, 9):
            tarjeta[hoyo] = PAR - 1
        match = await _played_match(qm_uow, course, user, scores_by_hole=tarjeta)

        await _use_case(social_uow, qm_uow, golf_course_uow, user_uow).execute(
            str(match.id.value)
        )

        eventos = await _feed_de(social_uow, user)
        birdies = [e for e in eventos if e.type == ActivityEventType.BIRDIE]
        assert len(birdies) == 1
        assert birdies[0].payload["count"] == 3
        assert birdies[0].payload["holes"] == [1, 5, 9]

    async def test_un_hoyo_en_uno_no_se_cuenta_ademas_como_eagle(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given un hoyo en uno en un par 4 / When se publica / Then va una vez."""
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        tarjeta = dict.fromkeys(range(1, 19), PAR)
        tarjeta[7] = 1
        match = await _played_match(qm_uow, course, user, scores_by_hole=tarjeta)

        await _use_case(social_uow, qm_uow, golf_course_uow, user_uow).execute(
            str(match.id.value)
        )

        tipos = [e.type for e in await _feed_de(social_uow, user)]
        assert ActivityEventType.HOLE_IN_ONE in tipos
        assert ActivityEventType.EAGLE_OR_BETTER not in tipos

    async def test_una_vuelta_sin_nada_que_contar_no_publica(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given una vuelta de pares en un campo ya conocido / When se publica /
        Then el feed no se entera: jugar bien sin destacar no es noticia.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        anterior = await _played_match(qm_uow, course, user)
        match = await _played_match(qm_uow, course, user)
        history = _CourseHistoryFake()
        history.registra(user.id, str(course.id.value), str(anterior.id.value))

        publicados = await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow, history=history
        ).execute(str(match.id.value))

        assert publicados == 0

    async def test_estrenar_campo_se_publica_solo_la_primera_vez(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given dos vueltas en el mismo campo / When se publican / Then solo la primera estrena."""
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        history = _CourseHistoryFake()
        use_case = _use_case(social_uow, qm_uow, golf_course_uow, user_uow, history=history)

        primera = await _played_match(qm_uow, course, user)
        await use_case.execute(str(primera.id.value))
        history.registra(user.id, str(course.id.value), str(primera.id.value))
        segunda = await _played_match(qm_uow, course, user)
        await use_case.execute(str(segunda.id.value))

        estrenos = [
            e for e in await _feed_de(social_uow, user) if e.type == ActivityEventType.NEW_COURSE
        ]
        assert len(estrenos) == 1
        assert estrenos[0].source_match_id == str(primera.id.value)

    async def test_publica_record_personal_cuando_baja_su_mejor_diferencial(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given un jugador cuyo mejor diferencial ha bajado tras esta vuelta /
        When se publica / Then sale el record con el anterior y el nuevo.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        match = await _played_match(qm_uow, course, user)
        differentials = _DifferentialsStub({str(user.id.value): 12.4})

        await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow, differentials
        ).execute(str(match.id.value), best_differential_before={str(user.id.value): 15.1})

        records = [
            e
            for e in await _feed_de(social_uow, user)
            if e.type == ActivityEventType.PERSONAL_BEST
        ]
        assert len(records) == 1
        assert records[0].payload["differential"] == "12.4"
        assert records[0].payload["previous_best"] == "15.1"

    async def test_no_publica_record_si_no_mejoro(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given una vuelta que no baja su mejor marca / When se publica / Then no hay record."""
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        match = await _played_match(qm_uow, course, user)
        differentials = _DifferentialsStub({str(user.id.value): 15.1})

        await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow, differentials
        ).execute(str(match.id.value), best_differential_before={str(user.id.value): 15.1})

        tipos = [e.type for e in await _feed_de(social_uow, user)]
        assert ActivityEventType.PERSONAL_BEST not in tipos

    async def test_la_primera_vuelta_con_diferencial_no_es_un_record(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given un jugador sin diferencial previo / When cierra su primera vuelta /
        Then no se anuncia como record: es el punto de partida.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        match = await _played_match(qm_uow, course, user)
        differentials = _DifferentialsStub({str(user.id.value): 15.1})

        await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow, differentials
        ).execute(str(match.id.value), best_differential_before={str(user.id.value): None})

        tipos = [e.type for e in await _feed_de(social_uow, user)]
        assert ActivityEventType.PERSONAL_BEST not in tipos


class TestQuienPublica:
    async def test_publica_para_todos_los_participantes_con_cuenta(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given dos jugadores registrados en la partida / When se publica / Then
        cada uno tiene su entrada: el birdie es de quien lo hizo.
        """
        creador = await _create_user(user_uow)
        amigo = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, creador.id)
        tarjeta = dict.fromkeys(range(1, 19), PAR)
        tarjeta[3] = PAR - 1
        match = await _played_match(
            qm_uow,
            course,
            creador,
            scores_by_hole=tarjeta,
            others=[QuickMatchParticipant.for_user(amigo.id)],
        )

        await _use_case(social_uow, qm_uow, golf_course_uow, user_uow).execute(
            str(match.id.value)
        )

        assert [e.type for e in await _feed_de(social_uow, creador)].count(
            ActivityEventType.BIRDIE
        ) == 1
        assert [e.type for e in await _feed_de(social_uow, amigo)].count(
            ActivityEventType.BIRDIE
        ) == 1

    async def test_no_publica_de_quien_lo_tiene_apagado(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given un jugador con la publicacion apagada / When se publica / Then no aparece."""
        callado = await _create_user(user_uow, share_activity=False)
        course = await _create_course(golf_course_uow, callado.id)
        match = await _played_match(qm_uow, course, callado)

        publicados = await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow
        ).execute(str(match.id.value))

        assert publicados == 0
        assert await _feed_de(social_uow, callado) == []

    async def test_los_invitados_no_generan_eventos(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given una partida con un invitado sin cuenta / When se publica / Then
        solo se publica lo del registrado: el invitado no tiene feed.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        invitado = QuickMatchParticipant.for_guest(
            first_name="Invitado", last_name="Sin Cuenta", handicap=20.0
        )
        match = await _played_match(qm_uow, course, user, others=[invitado])

        publicados = await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow
        ).execute(str(match.id.value))

        assert publicados == 1  # solo el NEW_COURSE del registrado


class TestQueNoSePublica:
    async def test_una_tarjeta_incompleta_no_llega_al_feed(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given una vuelta abandonada a los 12 hoyos / When se publica / Then no
        se publica nada: si no vale para la media, no vale para presumir.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        tarjeta = dict.fromkeys(range(1, 13), PAR)
        tarjeta[3] = PAR - 1
        match = await _played_match(qm_uow, course, user, scores_by_hole=tarjeta)

        publicados = await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow
        ).execute(str(match.id.value))

        assert publicados == 0

    async def test_media_vuelta_limpia_si_cuenta(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given los nueve de ida enteros / When se publica / Then el birdie cuenta."""
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        tarjeta = dict.fromkeys(range(1, 10), PAR)
        tarjeta[2] = PAR - 1
        match = await _played_match(qm_uow, course, user, scores_by_hole=tarjeta)

        await _use_case(social_uow, qm_uow, golf_course_uow, user_uow).execute(
            str(match.id.value)
        )

        eventos = await _feed_de(social_uow, user)
        birdies = [e for e in eventos if e.type == ActivityEventType.BIRDIE]
        assert len(birdies) == 1
        assert birdies[0].payload["holes_played"] == 9

    async def test_una_partida_sin_terminar_no_publica(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given una partida en juego / When se intenta publicar / Then no se
        publica: los logros salen de vueltas terminadas.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        match = await _played_match(qm_uow, course, user, complete=False)

        publicados = await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow
        ).execute(str(match.id.value))

        assert publicados == 0

    async def test_una_partida_que_no_existe_no_rompe(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """Given un id que no existe / When se publica / Then devuelve cero sin fallar."""
        publicados = await _use_case(
            social_uow, qm_uow, golf_course_uow, user_uow
        ).execute(str(uuid4()))

        assert publicados == 0


class TestIdempotencia:
    async def test_publicar_dos_veces_la_misma_vuelta_no_duplica(
        self, social_uow, qm_uow, golf_course_uow, user_uow
    ):
        """
        Given una vuelta ya publicada / When se vuelve a procesar / Then el feed
        no crece: es el caso del movil reintentando sobre una conexion mala.
        """
        user = await _create_user(user_uow)
        course = await _create_course(golf_course_uow, user.id)
        tarjeta = dict.fromkeys(range(1, 19), PAR)
        tarjeta[1] = PAR - 1
        match = await _played_match(qm_uow, course, user, scores_by_hole=tarjeta)
        use_case = _use_case(social_uow, qm_uow, golf_course_uow, user_uow)

        await use_case.execute(str(match.id.value))
        await use_case.execute(str(match.id.value))

        eventos = await _feed_de(social_uow, user)
        assert len(eventos) == 2  # BIRDIE + NEW_COURSE, una sola vez cada uno
