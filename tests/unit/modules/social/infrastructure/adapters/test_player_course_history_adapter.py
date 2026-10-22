"""
Si un jugador ya habia pisado un campo (L9, tabla del 22 oct 2026): tambien en
los grupos de stroke play de sus torneos, no solo en partidas rapidas y partidos
de la Ryder.
"""

from datetime import datetime, timedelta

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
from src.modules.social.application.ports.player_course_history_interface import PlayedBefore
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.unit.modules.social.stroke_play_world import DIA, StrokePlayWorld, tarjeta

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world():
    return StrokePlayWorld(
        InMemoryCompetitionUnitOfWork(), InMemoryGolfCourseUnitOfWork(), InMemoryUserUnitOfWork()
    )


def _adapter(world) -> PlayerCourseHistoryAdapter:
    return PlayerCourseHistoryAdapter(InMemoryQuickMatchUnitOfWork(), world.comp)


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


async def test_a_previous_stroke_play_group_on_the_course_counts(world):
    ana, _, course, _ = await _jugado(world)

    assert await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta"
    )


async def test_the_group_being_judged_is_left_out(world):
    ana, _, course, partida = await _jugado(world)

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), str(partida.id.value)
    )


async def test_another_course_does_not_count(world):
    ana, _, _, _ = await _jugado(world)
    otro = await world.course(ana)

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(otro.id.value), "otra-vuelta"
    )


async def test_a_no_show_never_set_foot_on_the_course(world):
    _, bea, course, _ = await _jugado(world, bea=EstadoDeTarjeta.NO_PRESENTADO)

    assert not await _adapter(world).has_played_course_before(
        bea.id, str(course.id.value), "otra-vuelta"
    )


async def test_a_withdrawn_player_did_play_the_course(world):
    _, bea, course, _ = await _jugado(world, bea=EstadoDeTarjeta.RETIRADO)

    assert await _adapter(world).has_played_course_before(
        bea.id, str(course.id.value), "otra-vuelta"
    )


async def test_a_group_still_on_the_course_does_not_count(world):
    ana, _, course, _ = await _jugado(world, estado=EstadoPartida.IN_PROGRESS)

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta"
    )


# ==================== Decisiones del 22 oct: antes del torneo y solo los cerrados ====================


async def test_the_tournament_being_judged_never_counts(world):
    """Otra vuelta del mismo torneo en el campo no lo hace «ya jugado»."""
    ana, _, course, _ = await _jugado(world)
    competition = (await world.comp.partidas.completadas_de_jugadores([ana.id]))[0].competition_id

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", excluding_competition_id=str(competition.value)
    )


async def test_a_ryder_match_of_the_tournament_being_judged_never_counts(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    await world.match(await world.round(competition, course), ana, rival, tarjeta())

    assert await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta"
    )
    assert not await _adapter(world).has_played_course_before(
        ana.id,
        str(course.id.value),
        "otra-vuelta",
        excluding_competition_id=str(competition.id.value),
    )


async def test_a_group_of_a_tournament_still_open_does_not_count(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana], completed=False)
    course = await world.course(ana)
    await world.group(competition, await world.round(competition, course), {ana: tarjeta()})

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta"
    )


async def test_a_ryder_match_of_a_tournament_still_open_does_not_count(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(
        ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival], completed=False
    )
    course = await world.course(ana)
    await world.match(await world.round(competition, course), ana, rival, tarjeta())

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta"
    )


# ==================== Corte por fecha (revision final) ====================


async def test_only_rounds_before_the_cut_count(world):
    ana, _, course, _ = await _jugado(world)  # ronda del 1 jun 2026, torneo cerrado

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(DIA)
    )
    assert await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(DIA + timedelta(days=1))
    )


async def test_only_quick_matches_before_the_cut_count(world):
    ana = await world.user()
    course = await world.course(ana)
    qm_uow = InMemoryQuickMatchUnitOfWork()
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=ana.id,
        golf_course_id=course.id,
        scoring_format=ScoringFormat.STABLEFORD,
    )
    match.start([match.creator_participant_id])
    match.complete()
    async with qm_uow:
        await qm_uow.quick_matches.add(match)
    adapter = PlayerCourseHistoryAdapter(qm_uow, world.comp)
    hoy = match.created_at.date()

    assert not await adapter.has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(hoy)
    )
    assert await adapter.has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(hoy + timedelta(days=1))
    )


# ==================== El mismo dia, por hora real (22 oct, prueba de punta a punta) ====================

# La vuelta que se juzga: la sesion de la tarde (12:00 locales), que en Madrid en
# junio son las 10:00 UTC
TARDE = PlayedBefore(DIA, local_hour=12, utc_instant=datetime(2026, 6, 1, 10, 0))


async def _rapida_creada(world, ana, course, creada: datetime) -> PlayerCourseHistoryAdapter:
    qm_uow = InMemoryQuickMatchUnitOfWork()
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
    return PlayerCourseHistoryAdapter(qm_uow, world.comp)


@pytest.mark.parametrize(
    ("creada", "cuenta"),
    [
        (datetime(2026, 6, 1, 9, 59), True),  # antes de la sesion, el mismo dia
        (datetime(2026, 6, 1, 10, 0), False),  # a la vez: no es ANTES
        (datetime(2026, 6, 1, 10, 1), False),  # despues
        (datetime(2026, 5, 31, 23, 0), True),  # el dia anterior
    ],
)
async def test_a_quick_match_counts_by_its_creation_instant(world, creada, cuenta):
    ana = await world.user()
    course = await world.course(ana)
    adapter = await _rapida_creada(world, ana, course, creada)

    assert (
        await adapter.has_played_course_before(
            ana.id, str(course.id.value), "otra-vuelta", before=TARDE
        )
        is cuenta
    )


async def test_without_the_instant_a_quick_match_that_day_does_not_count(world):
    ana = await world.user()
    course = await world.course(ana)
    adapter = await _rapida_creada(world, ana, course, datetime(2026, 6, 1, 0, 1))

    assert not await adapter.has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(DIA, local_hour=12)
    )


async def test_a_quick_match_with_a_zone_is_compared_in_utc(world):
    """Un instante con zona se pasa a UTC antes de comparar."""
    from zoneinfo import ZoneInfo

    ana = await world.user()
    course = await world.course(ana)
    # 11:30 en Madrid = 9:30 UTC, antes de las 10:00 UTC
    adapter = await _rapida_creada(
        world, ana, course, datetime(2026, 6, 1, 11, 30, tzinfo=ZoneInfo("Europe/Madrid"))
    )

    assert await adapter.has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=TARDE
    )


async def _grupo_en_sesion(world, session: SessionType):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana])
    course = await world.course(ana)
    await world.group(
        competition, await world.round(competition, course, DIA, session), {ana: tarjeta()}
    )
    return ana, course


@pytest.mark.parametrize(
    ("sesion", "cuenta"),
    [
        (SessionType.MORNING, True),
        (SessionType.AFTERNOON, False),
        (SessionType.EVENING, False),
    ],
)
async def test_another_tournament_that_day_counts_by_its_session(world, sesion, cuenta):
    ana, course = await _grupo_en_sesion(world, sesion)

    assert (
        await _adapter(world).has_played_course_before(
            ana.id, str(course.id.value), "otra-vuelta", before=TARDE
        )
        is cuenta
    )


async def test_without_the_session_hour_another_tournament_that_day_does_not_count(world):
    ana, course = await _grupo_en_sesion(world, SessionType.MORNING)

    assert not await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(DIA)
    )


async def test_the_session_hour_is_enough_without_the_zone(world):
    """En el mismo campo la zona es la misma: el orden de las sesiones basta."""
    ana, course = await _grupo_en_sesion(world, SessionType.MORNING)

    assert await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=PlayedBefore(DIA, local_hour=12)
    )


async def test_a_ryder_match_that_morning_counts(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    await world.match(
        await world.round(competition, course, DIA, SessionType.MORNING), ana, rival, tarjeta()
    )

    assert await _adapter(world).has_played_course_before(
        ana.id, str(course.id.value), "otra-vuelta", before=TARDE
    )
