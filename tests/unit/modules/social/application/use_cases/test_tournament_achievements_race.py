"""
La publicacion de logros de un torneo frente a su reapertura (revision final,
22 oct 2026).

Calcular los logros lleva un rato y no se hace bajo el candado del torneo: en
ese hueco se puede reabrir, corregir una tarjeta y volver a cerrar. Lo que debe
quedar en el feed es siempre lo del ULTIMO cierre:

- Reabierto mientras se calculaba: no se publica nada.
- Reabierto, corregido y cerrado otra vez (con su propia publicacion) mientras
  la vieja seguia calculando: queda lo del ultimo cierre, no lo viejo.
- Una reapertura cuyo borrado fallo: el cierre siguiente sustituye lo viejo.
- Publicar dos veces el mismo cierre no toca lo que ya estaba igual.
"""

from datetime import datetime

import pytest

from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.social.infrastructure.adapters.player_differentials_adapter import (
    StatsPlayerDifferentialsAdapter,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from tests.unit.modules.social.stroke_play_world import MOMENTO, StrokePlayWorld, tarjeta

pytestmark = pytest.mark.asyncio

T = ActivityEventType


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def world():
    return StrokePlayWorld(
        InMemoryCompetitionUnitOfWork(), InMemoryGolfCourseUnitOfWork(), InMemoryUserUnitOfWork()
    )


class _Hueco(PlayerCourseHistoryInterface):
    """
    El historial de verdad, que la primera vez que se le pregunta ejecuta lo que
    se le diga: es el hueco entre leer el torneo y escribir sus logros.
    """

    def __init__(self, real: PlayerCourseHistoryInterface, en_el_hueco):
        self._real = real
        self._en_el_hueco = en_el_hueco

    async def has_played_course_before(self, *args, **kwargs) -> bool:
        if self._en_el_hueco is not None:
            accion, self._en_el_hueco = self._en_el_hueco, None
            await accion()
        return await self._real.has_played_course_before(*args, **kwargs)


def _publisher(world, social_uow, en_el_hueco=None) -> PublishTournamentAchievementsUseCase:
    stats = GetPlayerStatsUseCase(
        user_uow=world.users,
        competition_uow=world.comp,
        quick_match_uow=InMemoryQuickMatchUnitOfWork(),
        golf_course_uow=world.golf,
    )
    history = PlayerCourseHistoryAdapter(InMemoryQuickMatchUnitOfWork(), world.comp)
    return PublishTournamentAchievementsUseCase(
        social_uow=social_uow,
        competition_uow=world.comp,
        golf_course_uow=world.golf,
        user_uow=world.users,
        differentials=StatsPlayerDifferentialsAdapter(stats),
        history=_Hueco(history, en_el_hueco),
    )


async def _feed(social_uow, user):
    async with social_uow:
        return await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=100
        )


async def _tipos(social_uow, user):
    return sorted(e.type for e in await _feed(social_uow, user))


async def _torneo_con_birdie(world):
    ana = await world.user()
    competition = await world.competition(ana, enrolled=[ana])
    course = await world.course(ana)
    partida = await world.group(
        competition, await world.round(competition, course), {ana: tarjeta(h4=3)}
    )
    return ana, competition, partida


async def _reabrir(world, social_uow, competition, *, avisar: bool = True) -> None:
    competition.revert_to_in_progress()
    await world.save_competition(competition)
    if avisar:
        await PublishCompetitionNoticesUseCase(social_uow, world.users).reopened(
            str(competition.id.value)
        )


async def _quitar_el_birdie(world, ana, partida) -> None:
    async with world.comp:
        golpes = await world.comp.golpes_de_partida.de_la_partida(partida.id)
        hoyo = next(g for g in golpes if g.hoyo == 4)
        hoyo.anotar_propio(4, True, ana.id, MOMENTO)
        hoyo.anotar_del_marcador(4, True, ana.id, MOMENTO)
        await world.comp.golpes_de_partida.guardar(hoyo)


async def _cerrar(world, competition) -> None:
    competition.complete()
    await world.save_competition(competition)


class TestReopenedWhileComputing:
    async def test_reopened_meanwhile_publishes_nothing(self, world, social_uow):
        ana, competition, _ = await _torneo_con_birdie(world)

        async def reabrir():
            await _reabrir(world, social_uow, competition)

        publicados = await _publisher(world, social_uow, reabrir).execute(str(competition.id.value))

        assert publicados == 0
        assert await _feed(social_uow, ana) == []

    async def test_reopened_corrected_and_closed_again_meanwhile_leaves_the_last_close(
        self, world, social_uow
    ):
        ana, competition, partida = await _torneo_con_birdie(world)

        async def reabrir_corregir_y_cerrar():
            await _reabrir(world, social_uow, competition)
            await _quitar_el_birdie(world, ana, partida)
            await _cerrar(world, competition)
            await _publisher(world, social_uow).execute(str(competition.id.value))

        await _publisher(world, social_uow, reabrir_corregir_y_cerrar).execute(
            str(competition.id.value)
        )

        tipos = await _tipos(social_uow, ana)
        assert T.BIRDIE not in tipos
        assert tipos.count(T.FIRST_TOURNAMENT) == 1

    async def test_an_edit_that_keeps_it_closed_still_publishes(self, world, social_uow):
        """Otro cambio del torneo (ya cerrado) en el hueco: se recalcula y se publica."""
        ana, competition, _ = await _torneo_con_birdie(world)

        async def editar():
            competition._updated_at = datetime.now()
            await world.save_competition(competition)

        await _publisher(world, social_uow, editar).execute(str(competition.id.value))

        assert T.BIRDIE in await _tipos(social_uow, ana)


class TestTheLastCloseReplaces:
    async def test_a_reopening_whose_delete_failed_is_replaced_on_closing(self, world, social_uow):
        ana, competition, partida = await _torneo_con_birdie(world)
        await _publisher(world, social_uow).execute(str(competition.id.value))

        await _reabrir(world, social_uow, competition, avisar=False)
        await _quitar_el_birdie(world, ana, partida)
        await _cerrar(world, competition)
        await _publisher(world, social_uow).execute(str(competition.id.value))

        tipos = await _tipos(social_uow, ana)
        assert T.BIRDIE not in tipos
        assert tipos.count(T.FIRST_TOURNAMENT) == 1

    async def test_publishing_the_same_close_twice_keeps_what_was_there(self, world, social_uow):
        ana, competition, _ = await _torneo_con_birdie(world)
        publisher = _publisher(world, social_uow)
        await publisher.execute(str(competition.id.value))
        antes = {(e.type, e.id, e.published_at) for e in await _feed(social_uow, ana)}

        await publisher.execute(str(competition.id.value))

        assert {(e.type, e.id, e.published_at) for e in await _feed(social_uow, ana)} == antes

    async def test_other_tournaments_are_not_touched(self, world, social_uow):
        ana, otro, _ = await _torneo_con_birdie(world)
        await _publisher(world, social_uow).execute(str(otro.id.value))
        competition = await world.competition(ana, enrolled=[ana])
        course = await world.course(ana)
        await world.group(competition, await world.round(competition, course), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.BIRDIE in await _tipos(social_uow, ana)
