"""
Las lecturas en bloque de las partidas jugadas juntos, contra Postgres (BE-3).

| Caso                                                  | Resultado                          |
|-------------------------------------------------------|------------------------------------|
| Partidas rapidas de los dos, terminadas               | Salen                              |
| Oculta por uno u otro / en otro estado / sin el otro  | No salen                           |
| Golpes de varias partidas rapidas                     | Los suyos, en una lectura          |
| Partidos de torneo con los dos, por estado            | Solo los de esos estados           |
| Partido con solo uno de los dos                       | No sale                            |
| Grupos de stroke play con los dos y sus golpes        | Los suyos                          |
| Campos por ids                                        | Enteros: salidas y hoyos           |
"""

from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_hole_score_repository import (
    SQLAlchemyQuickMatchHoleScoreRepository,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_repository import (
    SQLAlchemyQuickMatchRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    jugadores,
    ronda,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_partida_repository import (
    _jugador,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AHORA = datetime(2026, 6, 1, 10, 0, 0)


async def _campo(db_session, creador: UserId) -> GolfCourse:
    course = GolfCourse.create(
        name=f"Juntos {uuid4().hex[:6]}",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creador,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    await GolfCourseRepository(db_session).save(course)
    await db_session.commit()
    return course


@pytest_asyncio.fixture
async def campo(db_session, jugadores) -> GolfCourse:  # noqa: F811
    return await _campo(db_session, jugadores[0])


async def _rapida(
    db_session,
    campo: GolfCourse,
    creador: UserId,
    otros: list[UserId],
    terminar: bool = True,
    oculta_por: UserId | None = None,
) -> QuickMatch:
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creador,
        golf_course_id=campo.id,
        scoring_format=ScoringFormat.STABLEFORD,
    )
    for otro in otros:
        match.add_participant(QuickMatchParticipant.for_user(otro))
    match.start(scorer_ids=[match.participants[0].participant_id])
    if terminar:
        match.complete()
    if oculta_por is not None:
        match.hide_for(ParticipantId(oculta_por.value))
    await SQLAlchemyQuickMatchRepository(db_session).add(match)
    await db_session.commit()
    return match


class TestPartidasRapidasDeLosDos:
    async def test_solo_las_terminadas_de_los_dos_que_nadie_oculto(
        self,
        db_session,
        jugadores,  # noqa: F811
        campo,
    ):
        yo, el, otro, _ = jugadores
        buena = await _rapida(db_session, campo, yo, [el])
        al_reves = await _rapida(db_session, campo, el, [yo, otro])
        await _rapida(db_session, campo, yo, [el], oculta_por=yo)
        await _rapida(db_session, campo, yo, [el], oculta_por=el)
        await _rapida(db_session, campo, yo, [el], terminar=False)
        await _rapida(db_session, campo, yo, [otro])

        leidas = await SQLAlchemyQuickMatchRepository(db_session).list_shared_by(
            yo, el, QuickMatchStatus.COMPLETED
        )

        assert {m.id for m in leidas} == {buena.id, al_reves.id}

    async def test_los_golpes_de_varias_partidas_en_una_lectura(
        self,
        db_session,
        jugadores,  # noqa: F811
        campo,
    ):
        yo, el, _, _ = jugadores
        partidas = [await _rapida(db_session, campo, yo, [el]) for _ in range(3)]
        repo = SQLAlchemyQuickMatchHoleScoreRepository(db_session)
        for numero, match in enumerate(partidas, start=1):
            await repo.add(
                QuickMatchHoleScore(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=match.id,
                    hole_number=numero,
                    participant_id=ParticipantId(yo.value),
                    score=4,
                    recorded_by_participant_id=ParticipantId(yo.value),
                )
            )
        await db_session.commit()

        leidos = await repo.find_by_matches([partidas[0].id, partidas[2].id])

        assert sorted((h.quick_match_id, h.hole_number) for h in leidos) == sorted(
            [(partidas[0].id, 1), (partidas[2].id, 3)]
        )
        assert await repo.find_by_matches([]) == []


def _jugador_de_partido(user_id: UserId) -> MatchPlayer:
    return MatchPlayer(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=(),
    )


class TestPartidosDeTorneoDeLosDos:
    async def test_por_estado_y_con_los_dos(
        self,
        db_session,
        jugadores,  # noqa: F811
        ronda,  # noqa: F811
    ):
        yo, el, otro, cuarto = jugadores
        uow = SQLAlchemyCompetitionUnitOfWork(db_session)

        def partido(numero, a, b):
            return Match.create(
                round_id=ronda.id,
                match_number=numero,
                team_a_players=[_jugador_de_partido(u) for u in a],
                team_b_players=[_jugador_de_partido(u) for u in b],
            )

        contrarios = partido(1, [yo, otro], [el, cuarto])
        contrarios.start()
        contrarios.complete({"winner": "A", "score": "2&1"})
        companeros = partido(2, [otro, cuarto], [yo, el])
        companeros.start()
        companeros.concede("A")
        en_juego = partido(3, [yo], [el])
        en_juego.start()
        sin_el = partido(4, [yo], [otro])
        sin_el.start()
        sin_el.complete({"winner": "A", "score": "1UP"})
        for match in (contrarios, companeros, en_juego, sin_el):
            await uow.matches.add(match)
        await db_session.commit()

        leidos = await uow.matches.find_with_both_players(
            yo, el, (MatchStatus.COMPLETED, MatchStatus.CONCEDED)
        )

        assert {m.id for m in leidos} == {contrarios.id, companeros.id}


class TestGruposDeStrokePlayDeLosDos:
    async def test_los_grupos_con_los_dos_y_sus_golpes(
        self,
        db_session,
        jugadores,  # noqa: F811
        ronda,  # noqa: F811
    ):
        yo, el, otro, cuarto = jugadores
        uow = SQLAlchemyCompetitionUnitOfWork(db_session)
        juntos = Partida.crear(
            ronda.competition_id, ronda.id, 1, [_jugador(yo), _jugador(el), _jugador(otro)]
        )
        separados = Partida.crear(ronda.competition_id, ronda.id, 2, [_jugador(cuarto)])
        await uow.partidas.anadir([juntos, separados])
        await db_session.commit()
        for partida, user_id in ((juntos, yo), (juntos, el), (separados, cuarto)):
            golpe = GolpeDePartida.crear(
                partida.id, ronda.id, ronda.competition_id, user_id, 1, AHORA
            )
            golpe.anotar_propio(4, True, user_id, AHORA)
            await uow.golpes_de_partida.guardar(golpe)
        await db_session.commit()

        grupos = await uow.partidas.con_los_dos(yo, el)
        golpes = await uow.golpes_de_partida.de_las_partidas([juntos.id])

        assert [g.id for g in grupos] == [juntos.id]
        assert {(g.partida_id, g.user_id) for g in golpes} == {(juntos.id, yo), (juntos.id, el)}
        assert await uow.golpes_de_partida.de_las_partidas([]) == []
        assert await uow.partidas.con_los_dos(yo, cuarto) == []


class TestCamposEnBloque:
    async def test_enteros_con_salidas_y_hoyos(self, db_session, jugadores):  # noqa: F811
        uno = await _campo(db_session, jugadores[0])
        otro = await _campo(db_session, jugadores[0])
        await _campo(db_session, jugadores[0])
        db_session.expunge_all()

        leidos = await GolfCourseRepository(db_session).find_by_ids([uno.id, otro.id])

        assert {c.id for c in leidos} == {uno.id, otro.id}
        for course in leidos:
            assert len(course.hole_card_for(TeeColor.YELLOW, Gender.MALE)) == 18
        assert await GolfCourseRepository(db_session).find_by_ids([]) == []
