"""
Si un jugador ya habia pisado un campo (L9, tabla del 22 oct 2026): tambien en
los grupos de stroke play de sus torneos, no solo en partidas rapidas y partidos
de la Ryder.
"""

import pytest

from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from tests.unit.modules.social.stroke_play_world import StrokePlayWorld, tarjeta

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
