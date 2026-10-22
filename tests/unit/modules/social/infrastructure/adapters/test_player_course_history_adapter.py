"""
Las vueltas en que un jugador piso un campo (L9 y logros exclusivos del 22 oct
2026): al menos un hoyo jugado en partidas rapidas terminadas, partidos de la
Ryder y grupos de stroke play de torneos CERRADOS, fechados en hora real.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.hole_score import HoleScore
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
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.exclusive_achievements import (
    PlayedRound,
    first_on_each_course,
    round_instant,
)
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.unit.modules.social.stroke_play_world import DIA, MOMENTO, StrokePlayWorld, tarjeta

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
    return PlayerCourseHistoryAdapter(
        qm_uow or InMemoryQuickMatchUnitOfWork(), world.comp, world.golf
    )


async def _primera(world, user, course, qm_uow=None) -> PlayedRound | None:
    """La primera vez que piso ese campo, segun el historial."""
    rondas = await _adapter(world, qm_uow).played_rounds([user.id])
    return first_on_each_course(rondas).get((user.id, str(course.id.value)))


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


async def _rapida(qm_uow, ana, course, creada: datetime, hoyos: int = 1, **estado) -> QuickMatch:
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=ana.id,
        golf_course_id=course.id,
        scoring_format=ScoringFormat.STABLEFORD,
    )
    match.start([match.creator_participant_id])
    if estado.get("terminada", True):
        match.complete()
    match = QuickMatch.reconstruct(
        id=match.id,
        creator_id=match.creator_id,
        golf_course_id=match.golf_course_id,
        match_format=match.match_format,
        status=match.status,
        participants=list(match.participants),
        scoring_format=match.scoring_format,
        hidden_by_participant_ids=estado.get("oculta_para"),
        created_at=creada,
        updated_at=creada,
    )
    async with qm_uow:
        await qm_uow.quick_matches.add(match)
        for hoyo in range(1, hoyos + 1):
            await qm_uow.quick_match_hole_scores.add(
                QuickMatchHoleScore(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=match.id,
                    hole_number=hoyo,
                    participant_id=match.creator_participant_id,
                    score=None if hoyo == 2 else 4,
                    recorded_by_participant_id=match.creator_participant_id,
                )
            )
    return match


# ==================== Que vueltas cuentan ====================


async def test_a_stroke_play_group_of_a_closed_tournament_counts(world):
    ana, bea, course, partida = await _jugado(world)

    primera = await _primera(world, ana, course)

    assert primera == PlayedRound(
        user_id=ana.id,
        golf_course_id=str(course.id.value),
        instant=datetime(2026, 6, 1, 6, 0),
        source_id=str(partida.id.value),
        holes_played=18,
        competition_id=str(partida.competition_id.value),
        kind="TEE_GROUP",
        player_ids=tuple(sorted(str(u.id.value) for u in (ana, bea))),
        round_date=DIA,
    )


async def test_another_course_does_not_count(world):
    ana, _, _, _ = await _jugado(world)
    otro = await world.course(ana)

    assert await _primera(world, ana, otro) is None


async def test_a_no_show_never_set_foot_on_the_course(world):
    _, bea, course, _ = await _jugado(world, bea=EstadoDeTarjeta.NO_PRESENTADO)

    assert await _primera(world, bea, course) is None


async def test_a_withdrawn_player_with_holes_did_play_the_course(world):
    _, bea, course, partida = await _jugado(world, bea=EstadoDeTarjeta.RETIRADO)

    primera = await _primera(world, bea, course)

    assert primera is not None
    assert primera.source_id == str(partida.id.value)


async def test_a_group_without_any_hole_of_his_does_not_count(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana])
    course = await world.course(ana)
    await world.group(
        competition,
        await world.round(competition, course),
        {ana: {}},
        estados={ana: EstadoDeTarjeta.RETIRADO},
    )

    assert await _primera(world, ana, course) is None


async def test_a_group_still_on_the_course_does_not_count(world):
    ana, _, course, _ = await _jugado(world, estado=EstadoPartida.IN_PROGRESS)

    assert await _primera(world, ana, course) is None


async def test_a_ryder_match_won_4_and_3_counts_its_15_holes(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    partido = await world.match(
        await world.round(competition, course), ana, rival, dict.fromkeys(range(1, 16), 4)
    )

    primera = await _primera(world, ana, course)

    assert primera is not None
    assert (primera.source_id, primera.competition_id, primera.kind, primera.holes_played) == (
        str(partido.id.value),
        str(competition.id.value),
        "MATCH",
        15,
    )


async def test_a_conceded_ryder_match_with_holes_counts(world):
    """Agustin, 22 oct: concedido con hoyos jugados piso el campo; sin hoyos, no."""
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    otro = await world.course(ana)
    partido = await world.match(
        await world.round(competition, course), ana, rival, {1: 4, 2: 5}, concedido=True
    )
    await world.match(await world.round(competition, otro), ana, rival, {}, concedido=True)

    primera = await _primera(world, ana, course)

    assert primera is not None
    assert (primera.source_id, primera.holes_played) == (str(partido.id.value), 2)
    assert await _primera(world, ana, otro) is None


async def test_a_ryder_match_without_any_hole_of_his_does_not_count(world):
    ana = await world.user()
    rival = await world.user()
    competition = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    await world.match(await world.round(competition, course), ana, rival, {})

    assert await _primera(world, ana, course) is None


async def test_holes_nobody_entered_do_not_count(world):
    """Las filas que la Ryder crea por adelantado y los golpes sin apuntar no son hoyos jugados."""
    ana = await world.user()
    rival = await world.user()
    ryder = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
    course = await world.course(ana)
    partido = await world.match(await world.round(ryder, course), ana, rival, {})
    stroke = await world.competition(ana, enrolled=[ana])
    ronda = await world.round(stroke, course)
    grupo = await world.group(stroke, ronda, {ana: {}}, estados={ana: EstadoDeTarjeta.RETIRADO})
    async with world.comp:
        for hoyo in range(1, 19):
            await world.comp.hole_scores.add(
                HoleScore.create(
                    match_id=partido.id,
                    hole_number=hoyo,
                    player_user_id=ana.id,
                    team="A",
                    strokes_received=0,
                )
            )
            await world.comp.golpes_de_partida.guardar(
                GolpeDePartida.crear(grupo.id, ronda.id, stroke.id, ana.id, hoyo, MOMENTO)
            )

    assert await _primera(world, ana, course) is None


async def test_a_group_of_a_tournament_still_open_does_not_count(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana], completed=False)
    course = await world.course(ana)
    await world.group(competition, await world.round(competition, course), {ana: tarjeta()})

    assert await _primera(world, ana, course) is None


async def test_a_cancelled_tournament_does_not_count(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana], completed=False)
    course = await world.course(ana)
    await world.group(competition, await world.round(competition, course), {ana: tarjeta()})
    competition.cancel()
    await world.save_competition(competition)

    assert await _primera(world, ana, course) is None


async def test_a_completed_quick_match_with_a_hole_counts_by_its_creation(world, qm_uow):
    ana = await world.user()
    course = await world.course(ana)
    partida = await _rapida(qm_uow, ana, course, datetime(2026, 6, 1, 7, 30), hoyos=12)

    assert await _primera(world, ana, course, qm_uow) == PlayedRound(
        user_id=ana.id,
        golf_course_id=str(course.id.value),
        instant=datetime(2026, 6, 1, 7, 30),
        source_id=str(partida.id.value),
        holes_played=12,
    )


async def test_a_quick_match_without_holes_or_unfinished_does_not_count(world, qm_uow):
    ana = await world.user()
    course = await world.course(ana)
    await _rapida(qm_uow, ana, course, datetime(2026, 6, 1, 7), hoyos=0)
    await _rapida(qm_uow, ana, course, datetime(2026, 6, 1, 8), terminada=False)

    assert await _primera(world, ana, course, qm_uow) is None


async def test_a_quick_match_in_his_trash_still_counts(world, qm_uow):
    ana = await world.user()
    course = await world.course(ana)
    partida = await _rapida(
        qm_uow, ana, course, datetime(2026, 6, 1, 7), oculta_para=[ParticipantId(ana.id.value)]
    )

    primera = await _primera(world, ana, course, qm_uow)

    assert primera is not None
    assert primera.source_id == str(partida.id.value)


async def test_everything_counts_however_old(world, qm_uow):
    """Sin tope: la mas antigua de 205 partidas sigue ahi."""
    ana = await world.user()
    course = await world.course(ana)
    otro = await world.course(ana)
    primera = await _rapida(qm_uow, ana, course, datetime(2020, 1, 1))
    for dia in range(205):
        await _rapida(qm_uow, ana, otro, datetime(2021, 1, 1) + timedelta(days=dia))

    encontrada = await _primera(world, ana, course, qm_uow)

    assert encontrada is not None
    assert encontrada.source_id == str(primera.id.value)


async def test_a_quick_match_with_a_zone_is_taken_to_utc(world, qm_uow):
    ana = await world.user()
    course = await world.course(ana)
    await _rapida(qm_uow, ana, course, datetime(2026, 6, 1, 11, 30, tzinfo=ZoneInfo(MADRID)))

    primera = await _primera(world, ana, course, qm_uow)

    assert primera is not None
    assert primera.instant == datetime(2026, 6, 1, 9, 30)


async def test_several_players_in_one_go(world):
    ana, bea, _, partida = await _jugado(world)

    rondas = await _adapter(world).played_rounds([ana.id, bea.id])

    assert sorted((r.user_id == ana.id, r.source_id) for r in rondas) == [
        (False, str(partida.id.value)),
        (True, str(partida.id.value)),
    ]
    assert await _adapter(world).played_rounds([]) == []


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

    primera = await _primera(world, ana, course, qm_uow)

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


def test_with_a_zone_and_no_session_it_is_midday_in_the_zone():
    """Revisor: una ronda antigua sin sesion, a mediodia local, no UTC."""
    assert round_instant(DIA, None, MADRID) == datetime(2026, 6, 1, 10, 0)
    assert round_instant(DIA, None, None) == datetime(2026, 6, 1, 12, 0)
    assert round_instant(DIA, SessionType.MORNING, MADRID) == datetime(2026, 6, 1, 4, 0)


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


def test_the_key_orders_by_instant_then_tournament_then_source():
    def _ronda(hora, origen, torneo=None):
        return PlayedRound(UserId.generate(), "c", datetime(2026, 6, 1, hora), origen, 1, torneo)

    temprano = _ronda(6, "z", "z")
    tarde_menor = _ronda(7, "b", "a")
    tarde_mayor = _ronda(7, "a", "b")
    rapida = _ronda(7, "c")

    assert sorted([rapida, tarde_mayor, tarde_menor, temprano], key=lambda v: v.key) == [
        temprano,
        tarde_menor,
        tarde_mayor,
        rapida,
    ]
