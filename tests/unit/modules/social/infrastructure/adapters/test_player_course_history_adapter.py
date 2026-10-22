"""
La primera vuelta de un jugador en un campo (L9 y logros exclusivos del 22 oct
2026): partidas rapidas, partidos de la Ryder y grupos de stroke play de
torneos CERRADOS, fechados en hora real.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.ports.player_course_history_interface import CourseRound
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.unit.modules.social.stroke_play_world import DIA, StrokePlayWorld, tarjeta

pytestmark = pytest.mark.asyncio

MADRID = "Europe/Madrid"  # en junio, UTC+2


@pytest.fixture
def world():
    return StrokePlayWorld(
        InMemoryCompetitionUnitOfWork(), InMemoryGolfCourseUnitOfWork(), InMemoryUserUnitOfWork()
    )


@pytest.fixture
def qm_uow():
    return InMemoryQuickMatchUnitOfWork()


def _adapter(world, qm_uow=None) -> PlayerCourseHistoryAdapter:
    return PlayerCourseHistoryAdapter(qm_uow or InMemoryQuickMatchUnitOfWork(), world.comp)


async def _primera(world, user, course, qm_uow=None, timezone=None) -> CourseRound | None:
    return await _adapter(world, qm_uow).first_round_on_course(
        user.id, str(course.id.value), timezone
    )


async def _jugado(world, bea: EstadoDeTarjeta | None = None, **grupo):
    """
    Ana y Bea juegan un grupo de stroke play, Bea con la tarjeta en el estado
    que se diga. Devuelve (ana, bea, campo, grupo).
    """
    ana = await world.user()
    estado_de_bea = bea
    bea = await world.user()
    if estado_de_bea is not None:
        grupo["estados"] = {bea: estado_de_bea}
    competition = await world.competition(ana, enrolled=[ana, bea])
    course = await world.course(ana)
    round_ = await world.round(competition, course)
    partida = await world.group(competition, round_, {ana: tarjeta(), bea: tarjeta()}, **grupo)
    return ana, bea, course, partida


async def _rapida(qm_uow, ana, course, creada: datetime) -> QuickMatch:
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=ana.id,
        golf_course_id=course.id,
        scoring_format=ScoringFormat.STABLEFORD,
    )
    match.start([match.creator_participant_id])
    match.complete()
    match = QuickMatch.reconstruct(
        id=match.id,
        creator_id=match.creator_id,
        golf_course_id=match.golf_course_id,
        match_format=match.match_format,
        status=match.status,
        participants=list(match.participants),
        scoring_format=match.scoring_format,
        created_at=creada,
        updated_at=creada,
    )
    async with qm_uow:
        await qm_uow.quick_matches.add(match)
    return match


# ==================== Que vueltas cuentan ====================


async def test_a_stroke_play_group_of_a_closed_tournament_counts(world):
    ana, _, course, partida = await _jugado(world)

    primera = await _primera(world, ana, course)

    assert primera == CourseRound(
        instant=datetime(2026, 6, 1, 6, 0),
        source_id=str(partida.id.value),
        competition_id=str(partida.competition_id.value),
    )


async def test_another_course_does_not_count(world):
    ana, _, _, _ = await _jugado(world)
    otro = await world.course(ana)

    assert await _primera(world, ana, otro) is None


async def test_a_no_show_never_set_foot_on_the_course(world):
    _, bea, course, _ = await _jugado(world, bea=EstadoDeTarjeta.NO_PRESENTADO)

    assert await _primera(world, bea, course) is None


async def test_a_withdrawn_player_did_play_the_course(world):
    _, bea, course, partida = await _jugado(world, bea=EstadoDeTarjeta.RETIRADO)

    primera = await _primera(world, bea, course)

    assert primera is not None
    assert primera.source_id == str(partida.id.value)


async def test_a_group_still_on_the_course_does_not_count(world):
    ana, _, course, _ = await _jugado(world, estado=EstadoPartida.IN_PROGRESS)

    assert await _primera(world, ana, course) is None


async def test_a_ryder_match_of_a_closed_tournament_counts(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    partido = await world.match(await world.round(competition, course), ana, rival, tarjeta())

    primera = await _primera(world, ana, course)

    assert primera is not None
    assert (primera.source_id, primera.competition_id) == (
        str(partido.id.value),
        str(competition.id.value),
    )


async def test_a_group_of_a_tournament_still_open_does_not_count(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana], completed=False)
    course = await world.course(ana)
    await world.group(competition, await world.round(competition, course), {ana: tarjeta()})

    assert await _primera(world, ana, course) is None


async def test_a_ryder_match_of_a_tournament_still_open_does_not_count(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(
        ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival], completed=False
    )
    course = await world.course(ana)
    await world.match(await world.round(competition, course), ana, rival, tarjeta())

    assert await _primera(world, ana, course) is None


async def test_a_cancelled_tournament_does_not_count(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana], completed=False)
    course = await world.course(ana)
    await world.group(competition, await world.round(competition, course), {ana: tarjeta()})
    competition.cancel()
    await world.save_competition(competition)

    assert await _primera(world, ana, course) is None


async def test_a_completed_quick_match_counts_by_its_creation(world, qm_uow):
    ana = await world.user()
    course = await world.course(ana)
    partida = await _rapida(qm_uow, ana, course, datetime(2026, 6, 1, 7, 30))

    assert await _primera(world, ana, course, qm_uow) == CourseRound(
        instant=datetime(2026, 6, 1, 7, 30), source_id=str(partida.id.value)
    )


async def test_a_quick_match_with_a_zone_is_taken_to_utc(world, qm_uow):
    ana = await world.user()
    course = await world.course(ana)
    await _rapida(qm_uow, ana, course, datetime(2026, 6, 1, 11, 30, tzinfo=ZoneInfo(MADRID)))

    primera = await _primera(world, ana, course, qm_uow)

    assert primera is not None
    assert primera.instant == datetime(2026, 6, 1, 9, 30)


# ==================== Cual es la primera ====================


@pytest.mark.parametrize(
    ("creada", "gana_la_rapida"),
    [
        (datetime(2026, 6, 1, 9, 59), True),  # antes de la sesion de la tarde (10:00 UTC)
        (datetime(2026, 6, 1, 10, 1), False),  # despues
        (datetime(2026, 5, 31, 23, 0), True),  # el dia anterior
    ],
)
async def test_the_oldest_by_real_time_in_the_course_zone(world, qm_uow, creada, gana_la_rapida):
    ana = await world.user()
    course = await world.course(ana, timezone=MADRID)
    competition = await world.competition(ana, enrolled=[ana])
    grupo = await world.group(
        competition,
        await world.round(competition, course, DIA, SessionType.AFTERNOON),
        {ana: tarjeta()},
    )
    partida = await _rapida(qm_uow, ana, course, creada)

    primera = await _primera(world, ana, course, qm_uow, timezone=MADRID)

    assert primera is not None
    esperada = partida if gana_la_rapida else grupo
    assert primera.source_id == str(esperada.id.value)


async def test_without_a_zone_the_session_hour_is_taken_as_utc(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana])
    course = await world.course(ana)
    await world.group(
        competition,
        await world.round(competition, course, DIA, SessionType.EVENING),
        {ana: tarjeta()},
    )

    primera = await _primera(world, ana, course)

    assert primera is not None
    assert primera.instant == datetime(2026, 6, 1, 18, 0)


async def test_the_morning_session_of_another_tournament_goes_first(world):
    ana = await world.user()
    course = await world.course(ana)
    tarde = await world.competition(ana, enrolled=[ana])
    await world.group(
        tarde, await world.round(tarde, course, DIA, SessionType.AFTERNOON), {ana: tarjeta()}
    )
    manana = await world.competition(ana, enrolled=[ana])
    grupo = await world.group(
        manana, await world.round(manana, course, DIA, SessionType.MORNING), {ana: tarjeta()}
    )

    primera = await _primera(world, ana, course)

    assert primera is not None
    assert primera.source_id == str(grupo.id.value)


async def test_in_the_same_session_the_lower_tournament_id_goes_first(world):
    ana = await world.user()
    course = await world.course(ana)
    uno = await world.competition(ana, enrolled=[ana])
    otro = await world.competition(ana, enrolled=[ana])
    for torneo in (uno, otro):
        await world.group(torneo, await world.round(torneo, course), {ana: tarjeta()})

    primera = await _primera(world, ana, course)

    assert primera is not None
    assert primera.competition_id == min(str(uno.id.value), str(otro.id.value))


async def test_the_key_orders_by_instant_then_tournament_then_source():
    temprano = CourseRound(datetime(2026, 6, 1, 6), "z", "z")
    tarde_menor = CourseRound(datetime(2026, 6, 1, 7), "b", "a")
    tarde_mayor = CourseRound(datetime(2026, 6, 1, 7), "a", "b")
    rapida = CourseRound(datetime(2026, 6, 1, 7), "c")

    assert sorted([rapida, tarde_mayor, tarde_menor, temprano], key=lambda v: v.key) == [
        temprano,
        tarde_menor,
        tarde_mayor,
        rapida,
    ]
