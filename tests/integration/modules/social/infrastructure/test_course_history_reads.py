"""
El historial de campos contra Postgres (logros exclusivos, 22 oct 2026): las
lecturas por lotes de quien piso un campo, cuantas consultas cuestan, la marca
de la ultima publicacion de un torneo y el candado de jugador entre dos
sesiones de verdad.
"""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_hole_score_repository import (
    SQLAlchemyQuickMatchHoleScoreRepository,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_unit_of_work import (
    SQLAlchemyQuickMatchUnitOfWork,
)
from src.modules.social.application.exclusive_achievements import lock_players
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    BASE_DATE,
    jugadores,
    ronda,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_partida_repository import (
    _jugador,
)
from tests.integration.modules.social.infrastructure.test_shared_games_repositories import (  # noqa: F401
    AHORA,
    _campo,
    _competicion,
    _jugador_de_partido,
    _rapida,
    campo,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _adapter(db_session) -> PlayerCourseHistoryAdapter:
    return PlayerCourseHistoryAdapter(
        SQLAlchemyQuickMatchUnitOfWork(db_session),
        SQLAlchemyCompetitionUnitOfWork(db_session),
        SQLAlchemyGolfCourseUnitOfWork(db_session),
    )


async def _ronda_de_torneo_cerrado(db_session, curso, creador: UserId, tipo: TournamentType):
    competition = await _competicion(db_session, creador, tipo)
    competition.activate()
    competition.close_enrollments()
    competition.start()
    competition.complete()
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    await uow.competitions.update(competition)
    round_ = Round.create(
        competition_id=competition.id,
        golf_course_id=curso.id,
        round_date=BASE_DATE,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    await uow.rounds.add(round_)
    await db_session.commit()
    return competition, round_


async def _ryder_de(
    db_session, curso, a: UserId, b: UserId, hoyos: int, terminar: bool = True
) -> Match:
    """Un partido acabado de a contra b, con `hoyos` hoyos apuntados por a."""
    _, round_ = await _ronda_de_torneo_cerrado(db_session, curso, a, TournamentType.RYDER_CUP)
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    match = Match.create(
        round_id=round_.id,
        match_number=1,
        team_a_players=[_jugador_de_partido(a)],
        team_b_players=[_jugador_de_partido(b)],
    )
    match.start()
    if terminar:
        match.complete({"winner": "A", "score": "4&3"})
    await uow.matches.add(match)
    await db_session.commit()
    for hoyo in range(1, 19):
        hole = HoleScore.create(
            match_id=match.id,
            hole_number=hoyo,
            player_user_id=a,
            team="A",
            strokes_received=0,
        )
        if hoyo <= hoyos:
            hole.set_own_score(4)
        await uow.hole_scores.add(hole)
    await db_session.commit()
    return match


async def _grupo_de(db_session, curso, a: UserId, b: UserId, c: UserId | None = None) -> Partida:
    """
    Un grupo acabado: a con 3 hoyos y retirado, b no presentado y, si se da,
    c retirado con un golpe creado pero sin apuntar.
    """
    competition, round_ = await _ronda_de_torneo_cerrado(
        db_session, curso, a, TournamentType.STABLEFORD
    )
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    del_grupo = [a, b] + ([c] if c is not None else [])
    grupo = Partida.crear(competition.id, round_.id, 1, [_jugador(u) for u in del_grupo])
    await uow.partidas.anadir([grupo])
    await db_session.commit()
    if c is not None:
        await uow.golpes_de_partida.guardar(
            GolpeDePartida.crear(grupo.id, round_.id, competition.id, c, 1, AHORA)
        )
    for hoyo in range(1, 4):
        golpe = GolpeDePartida.crear(grupo.id, round_.id, competition.id, a, hoyo, AHORA)
        golpe.anotar_propio(None if hoyo == 3 else 5, True, a, AHORA)
        await uow.golpes_de_partida.guardar(golpe)
    grupo.cerrar(completas=[], sin_golpes=[b])
    await uow.partidas.guardar([grupo])
    await db_session.commit()
    return grupo


async def _hoyos_de_rapida(db_session, partida, user_id: UserId, hoyos: int) -> None:
    repo = SQLAlchemyQuickMatchHoleScoreRepository(db_session)
    for hoyo in range(1, hoyos + 1):
        await repo.add(
            QuickMatchHoleScore(
                id=QuickMatchHoleScoreId.generate(),
                quick_match_id=partida.id,
                hole_number=hoyo,
                participant_id=ParticipantId(user_id.value),
                score=4,
                recorded_by_participant_id=ParticipantId(user_id.value),
            )
        )
    await db_session.commit()


class TestWhoSteppedOnTheCourse:
    async def test_every_source_with_at_least_one_hole(
        self,
        db_session,
        jugadores,  # noqa: F811
        campo,  # noqa: F811
    ):
        a, b, c, _ = jugadores
        partido = await _ryder_de(db_session, campo, a, b, hoyos=15)
        sin_hoyos = await _ryder_de(db_session, campo, c, b, hoyos=0)
        grupo = await _grupo_de(db_session, campo, a, b, c)
        sin_terminar_ryder = await _ryder_de(db_session, campo, a, b, hoyos=10, terminar=False)
        en_la_papelera = await _rapida(db_session, campo, a, [], oculta_por=a)
        await _hoyos_de_rapida(db_session, en_la_papelera, a, 12)
        sin_terminar = await _rapida(db_session, campo, a, [], terminar=False)
        await _hoyos_de_rapida(db_session, sin_terminar, a, 5)

        rondas = await _adapter(db_session).played_rounds([a, b, c])

        assert sorted((r.source_id, r.kind, r.holes_played) for r in rondas) == sorted(
            [
                (str(partido.id.value), "MATCH", 15),
                (str(grupo.id), "TEE_GROUP", 3),
                (str(en_la_papelera.id.value), "QUICK_MATCH", 12),
            ]
        )
        assert str(sin_hoyos.id.value) not in {r.source_id for r in rondas}
        assert str(sin_terminar_ryder.id.value) not in {r.source_id for r in rondas}
        assert {r.user_id for r in rondas} == {a}

    async def test_the_same_statements_for_one_player_as_for_many(
        self,
        db_session,
        jugadores,  # noqa: F811
        campo,  # noqa: F811
    ):
        a, b, c, d = jugadores
        await _ryder_de(db_session, campo, a, b, hoyos=18)
        await _grupo_de(db_session, campo, a, b)
        suya = await _rapida(db_session, campo, a, [])
        await _hoyos_de_rapida(db_session, suya, a, 18)
        for user_id in (c, d):
            await _ryder_de(db_session, campo, user_id, b, hoyos=18)
            await _ryder_de(db_session, campo, user_id, a, hoyos=9)
            await _grupo_de(db_session, campo, user_id, b)
            otro_campo = await _campo(db_session, user_id)
            await _grupo_de(db_session, otro_campo, user_id, a)
            rapida = await _rapida(db_session, campo, user_id, [])
            await _hoyos_de_rapida(db_session, rapida, user_id, 18)

        async def _sentencias(user_ids) -> int:
            sentencias: list[str] = []

            def _cuenta(conn, cursor, statement, *args):
                sentencias.append(statement)

            db_session.expunge_all()
            event.listen(Engine, "before_cursor_execute", _cuenta)
            try:
                await _adapter(db_session).played_rounds(user_ids)
            finally:
                event.remove(Engine, "before_cursor_execute", _cuenta)
            return len(sentencias)

        assert await _sentencias([c, d, a]) == await _sentencias([a])


class TestLastPublished:
    async def test_the_latest_of_those_types_for_the_competition(
        self,
        db_session,
        jugadores,  # noqa: F811
    ):
        a = jugadores[0]
        repo = SQLAlchemyActivityEventRepository(db_session)

        def _logro(tipo, cuando, torneo="t-1"):
            return ActivityEvent.create(
                user_id=a,
                type=tipo,
                occurred_at=cuando,
                source_match_id=f"g-{tipo}-{cuando}",
                payload={"competition_id": torneo},
                published_at=cuando,
            )

        await repo.add_many(
            [
                _logro(ActivityEventType.BIRDIE, datetime(2026, 6, 1, 9)),
                _logro(ActivityEventType.NEW_COURSE, datetime(2026, 6, 1, 10)),
                _logro(ActivityEventType.BIRDIE, datetime(2026, 6, 1, 11), torneo="t-2"),
            ]
        )
        await db_session.commit()

        assert await repo.last_published_at("t-1", [ActivityEventType.BIRDIE]) == datetime(
            2026, 6, 1, 9
        )
        assert await repo.last_published_at(
            "t-1", [ActivityEventType.BIRDIE, ActivityEventType.NEW_COURSE]
        ) == datetime(2026, 6, 1, 10)
        assert await repo.last_published_at("t-3", [ActivityEventType.BIRDIE]) is None
        assert await repo.last_published_at("t-1", []) is None


class TestPlayerLockAcrossSessions:
    async def test_a_second_session_waits_for_the_player_lock(
        self,
        db_session,
        jugadores,  # noqa: F811
    ):
        """
        Una reapertura con el candado del torneo y de sus jugadores cogido: otra
        sesion que quiera publicar para ese jugador espera a que termine.
        """
        a, b, _, _ = jugadores
        await db_session.commit()
        primera = SQLAlchemyActivityEventRepository(db_session)
        async with AsyncSession(bind=db_session.bind) as otra_sesion:
            segunda = SQLAlchemyActivityEventRepository(otra_sesion)
            await primera.lock_scope("torneo-1")
            await lock_players(primera, [b, a])

            espera = asyncio.create_task(lock_players(segunda, [a]))
            await asyncio.sleep(0.5)
            assert not espera.done()

            # Otro jugador, desde otra sesion, no espera
            async with AsyncSession(bind=db_session.bind) as tercera_sesion:
                await asyncio.wait_for(
                    lock_players(SQLAlchemyActivityEventRepository(tercera_sesion), [jugadores[3]]),
                    timeout=2,
                )
                await tercera_sesion.commit()

            await db_session.commit()
            await asyncio.wait_for(espera, timeout=5)
            await otra_sesion.commit()
