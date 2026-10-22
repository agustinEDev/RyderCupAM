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
| J: competiciones con los dos, en grupos distintos     | Salen, una vez                     |
| Campos por ids                                        | Enteros: salidas y hoyos           |
| Rondas y competiciones por ids                        | Las pedidas, en una lectura        |
| Caso 19: torneos en 2 o en 6 competiciones            | Las mismas consultas               |
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
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
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
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
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_unit_of_work import (
    SQLAlchemyQuickMatchUnitOfWork,
)
from src.modules.social.infrastructure.adapters.shared_games_adapter import SharedGamesAdapter
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork as SQLAlchemyUserUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    BASE_DATE,
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

    async def test_j_las_competiciones_con_los_dos_aunque_en_grupos_distintos(
        self,
        db_session,
        jugadores,  # noqa: F811
        ronda,  # noqa: F811
    ):
        """Tabla del 22 oct 2026, J: el torneo cuenta entero, juntos o no en el grupo."""
        yo, el, otro, cuarto = jugadores
        uow = SQLAlchemyCompetitionUnitOfWork(db_session)
        await uow.partidas.anadir(
            [
                Partida.crear(ronda.competition_id, ronda.id, 1, [_jugador(yo), _jugador(otro)]),
                Partida.crear(ronda.competition_id, ronda.id, 2, [_jugador(el)]),
            ]
        )
        await db_session.commit()

        assert await uow.partidas.competiciones_con_los_dos(yo, el) == [ronda.competition_id]
        assert await uow.partidas.competiciones_con_los_dos(yo, cuarto) == []


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


class TestRondasYCompeticionesEnBloque:
    async def test_por_ids(self, db_session, jugadores, ronda):  # noqa: F811
        uow = SQLAlchemyCompetitionUnitOfWork(db_session)
        otra = await _competicion(db_session, jugadores[0])
        await _competicion(db_session, jugadores[0])
        # Otra ronda que no se pide
        await uow.rounds.add(
            Round.create(
                competition_id=otra.id,
                golf_course_id=ronda.golf_course_id,
                round_date=BASE_DATE,
                session_type=SessionType.AFTERNOON,
                match_format=MatchFormat.SINGLES,
            )
        )
        await db_session.commit()
        db_session.expunge_all()

        rondas = await uow.rounds.find_by_ids([ronda.id])
        competiciones = await uow.competitions.find_by_ids([ronda.competition_id, otra.id])

        assert [r.id for r in rondas] == [ronda.id]
        assert {c.id for c in competiciones} == {ronda.competition_id, otra.id}
        assert await uow.rounds.find_by_ids([]) == []
        assert await uow.competitions.find_by_ids([]) == []


async def _competicion(
    db_session, creador: UserId, tipo: TournamentType = TournamentType.RYDER_CUP
) -> Competition:
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creador,
        name=CompetitionName(f"Juntos Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A" if tipo.has_teams else None,
        team_2_name="Team B" if tipo.has_teams else None,
        tournament_type=tipo,
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()
    return competition


async def _torneos_juntos(db_session, campo: GolfCourse, a: UserId, b: UserId, veces: int):
    """`veces` partidos y `veces` grupos de a y b, cada uno en su competicion y su ronda."""
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    for _ in range(veces):
        for tipo in (TournamentType.RYDER_CUP, TournamentType.STABLEFORD):
            competition = await _competicion(db_session, a, tipo)
            round_ = Round.create(
                competition_id=competition.id,
                golf_course_id=campo.id,
                round_date=BASE_DATE,
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
            )
            await uow.rounds.add(round_)
            await db_session.commit()
            if tipo.has_teams:
                match = Match.create(
                    round_id=round_.id,
                    match_number=1,
                    team_a_players=[_jugador_de_partido(a)],
                    team_b_players=[_jugador_de_partido(b)],
                )
                match.start()
                match.complete({"winner": "A", "score": "1UP"})
                await uow.matches.add(match)
            else:
                grupo = Partida.crear(competition.id, round_.id, 1, [_jugador(a), _jugador(b)])
                grupo.cerrar(completas=[a, b])
                await uow.partidas.anadir([grupo])
            await db_session.commit()


async def _sentencias(db_session, a: UserId, b: UserId) -> tuple[int, int]:
    adapter = SharedGamesAdapter(
        SQLAlchemyQuickMatchUnitOfWork(db_session),
        SQLAlchemyCompetitionUnitOfWork(db_session),
        SQLAlchemyGolfCourseUnitOfWork(db_session),
        SQLAlchemyUserUnitOfWork(db_session),
    )
    sentencias: list[str] = []

    def _cuenta(conn, cursor, statement, *args):
        sentencias.append(statement)

    db_session.expunge_all()
    event.listen(Engine, "before_cursor_execute", _cuenta)
    try:
        partidas = await adapter.between(a, b)
    finally:
        event.remove(Engine, "before_cursor_execute", _cuenta)
    return len(partidas), len(sentencias)


class TestSinUnaConsultaPorRonda:
    async def test_las_mismas_consultas_con_una_competicion_que_con_seis(
        self,
        db_session,
        jugadores,  # noqa: F811
        campo,
    ):
        """
        Caso 19, en torneos: un partido y un grupo en dos competiciones, frente
        a tres y tres en seis / Then cuesta las mismas consultas.
        """
        a, b, c, d = jugadores
        await _torneos_juntos(db_session, campo, a, b, veces=1)
        await _torneos_juntos(db_session, campo, c, d, veces=3)

        pocas, con_pocas = await _sentencias(db_session, a, b)
        muchas, con_muchas = await _sentencias(db_session, c, d)

        assert (pocas, muchas) == (2, 6)
        assert con_muchas == con_pocas
