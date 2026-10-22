"""
Logros de un torneo de stroke play (bloque L, tabla del 22 oct 2026).

- L7: al cerrarse un torneo de grupos de salida se publican los mismos logros
  que en la Ryder: HIO, eagle, birdie, campo nuevo, primer torneo y mejor marca.
- L8: con las tarjetas VALIDADAS de los grupos; los no presentados y los
  retirados no cuentan.
- L9: el primer torneo mira tambien los torneos de stroke play anteriores.
- L11: el logro lleva lo necesario para abrir la tarjeta del grupo.
- L12: idempotente por la clave de origen (el grupo).
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CompleteCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
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
from src.modules.social.application.ports.player_course_history_interface import (
    CourseRound,
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
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
from src.modules.social.infrastructure.adapters.player_differentials_adapter import (
    StatsPlayerDifferentialsAdapter,
)
from src.modules.social.infrastructure.adapters.tournament_achievements_publisher import (
    TournamentAchievementsPublisher,
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
from tests.unit.modules.social.stroke_play_world import DIA, MOMENTO, StrokePlayWorld, tarjeta

pytestmark = pytest.mark.asyncio

T = ActivityEventType


class _Differentials(PlayerDifferentialsInterface):
    """`ahora`: el mejor diferencial de hoy; `antes`: el de antes del torneo."""

    def __init__(self, ahora: dict | None = None, antes: dict | None = None):
        self._ahora = ahora or {}
        self._antes = antes or {}

    async def best_differential(self, user_id, excluding_competition_id=None):
        fuente = self._antes if excluding_competition_id else self._ahora
        return fuente.get(str(user_id.value))


class _History(PlayerCourseHistoryInterface):
    """Sin historial: todo campo se estrena, salvo lo registrado."""

    def __init__(self):
        self.vueltas: set = set()
        self.preguntas: list = []

    async def first_round_on_course(self, user_id, golf_course_id, timezone):
        self.preguntas.append((user_id, golf_course_id))
        # Lo registrado se jugo hace mucho: es lo mas antiguo
        return next(
            (
                CourseRound(instant=datetime(2000, 1, 1), source_id=m)
                for u, c, m in sorted(self.vueltas)
                if u == str(user_id.value) and c == golf_course_id
            ),
            None,
        )


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def world():
    return StrokePlayWorld(
        InMemoryCompetitionUnitOfWork(), InMemoryGolfCourseUnitOfWork(), InMemoryUserUnitOfWork()
    )


def _publisher(world, social_uow, differentials=None, history=None):
    return PublishTournamentAchievementsUseCase(
        social_uow=social_uow,
        competition_uow=world.comp,
        golf_course_uow=world.golf,
        user_uow=world.users,
        differentials=differentials or _Differentials(),
        history=history or _History(),
    )


async def _feed(social_uow, user):
    async with social_uow:
        return await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=50
        )


async def _tipos(social_uow, user) -> list[ActivityEventType]:
    return sorted(e.type for e in await _feed(social_uow, user))


async def _torneo(world, golpes_por_jugador, **grupo):
    """Un torneo de stroke play cerrado, una ronda y un grupo con esas tarjetas."""
    jugadores = list(golpes_por_jugador)
    dia = grupo.pop("dia", DIA)
    competition = await world.competition(jugadores[0], enrolled=jugadores, start=dia)
    course = await world.course(jugadores[0], pars=grupo.pop("course_pars", None))
    round_ = await world.round(competition, course, dia)
    partida = await world.group(competition, round_, golpes_por_jugador, **grupo)
    return competition, course, partida


# ==================== L7 y L11: los logros y su payload ====================


class TestStrokePlayAchievements:
    async def test_a_birdie_in_a_group_is_published(self, world, social_uow):
        ana = await world.user()
        competition, _, _ = await _torneo(world, {ana: tarjeta(h4=3)})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.BIRDIE in await _tipos(social_uow, ana)

    async def test_the_payload_opens_the_group_card(self, world, social_uow):
        ana = await world.user()
        competition, course, partida = await _torneo(world, {ana: tarjeta(h4=3)})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        birdie = next(e for e in await _feed(social_uow, ana) if e.type == T.BIRDIE)
        assert birdie.source_match_id == str(partida.id.value)
        assert birdie.payload["from_tournament"] is True
        assert birdie.payload["kind"] == "TEE_GROUP"
        assert birdie.payload["group_id"] == str(partida.id.value)
        assert birdie.payload["competition_id"] == str(competition.id.value)
        assert birdie.payload["golf_course_id"] == str(course.id.value)
        assert birdie.payload["holes"] == [4]
        assert birdie.payload["holes_played"] == 18

    async def test_a_hole_in_one_in_a_group(self, world, social_uow):
        ana = await world.user()
        competition, _, _ = await _torneo(
            world, {ana: tarjeta(h3=1)}, course_pars={3: 3}, pars={3: 3}
        )

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.HOLE_IN_ONE in await _tipos(social_uow, ana)

    async def test_an_eagle_in_a_group(self, world, social_uow):
        ana = await world.user()
        competition, _, _ = await _torneo(world, {ana: tarjeta(h7=2)})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.EAGLE_OR_BETTER in await _tipos(social_uow, ana)

    async def test_new_course_asks_the_history_for_the_group(self, world, social_uow):
        ana = await world.user()
        competition, course, _ = await _torneo(world, {ana: tarjeta()})
        history = _History()

        await _publisher(world, social_uow, history=history).execute(str(competition.id.value))

        assert T.NEW_COURSE in await _tipos(social_uow, ana)
        assert (ana.id, str(course.id.value)) in history.preguntas

    async def test_course_already_played_is_not_new(self, world, social_uow):
        ana = await world.user()
        competition, course, _ = await _torneo(world, {ana: tarjeta()})
        history = _History()
        history.vueltas.add((str(ana.id.value), str(course.id.value), "otra-vuelta"))

        await _publisher(world, social_uow, history=history).execute(str(competition.id.value))

        assert T.NEW_COURSE not in await _tipos(social_uow, ana)

    async def test_first_tournament_is_published_once(self, world, social_uow):
        ana = await world.user()
        competition = await world.competition(ana, enrolled=[ana])
        course = await world.course(ana)
        primera = await world.round(competition, course)
        segunda = await world.round(competition, course, DIA + timedelta(days=1))
        await world.group(competition, primera, {ana: tarjeta()})
        await world.group(competition, segunda, {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert (await _tipos(social_uow, ana)).count(T.FIRST_TOURNAMENT) == 1

    async def test_personal_best_hangs_from_the_group(self, world, social_uow):
        ana = await world.user()
        competition, _, partida = await _torneo(world, {ana: tarjeta()})
        ahora = _Differentials({str(ana.id.value): 5.0}, antes={str(ana.id.value): 9.0})

        await _publisher(world, social_uow, differentials=ahora).execute(str(competition.id.value))

        record = next(e for e in await _feed(social_uow, ana) if e.type == T.PERSONAL_BEST)
        assert record.source_match_id == str(partida.id.value)
        assert record.payload["kind"] == "TEE_GROUP"

    async def test_each_player_of_the_group_gets_his_own(self, world, social_uow):
        ana = await world.user()
        bea = await world.user()
        competition, _, _ = await _torneo(world, {ana: tarjeta(h4=3), bea: tarjeta(h5=3)})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.BIRDIE in await _tipos(social_uow, ana)
        birdie_bea = next(e for e in await _feed(social_uow, bea) if e.type == T.BIRDIE)
        assert birdie_bea.payload["holes"] == [5]


# ==================== L8: lo que no cuenta ====================


class TestCardsThatDoNotCount:
    async def test_a_no_show_publishes_nothing(self, world, social_uow):
        ana = await world.user()
        bea = await world.user()
        competition, _, _ = await _torneo(
            world,
            {ana: tarjeta(), bea: tarjeta(h4=3)},
            estados={bea: EstadoDeTarjeta.NO_PRESENTADO},
        )

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert await _tipos(social_uow, bea) == []

    async def test_a_withdrawn_player_publishes_nothing(self, world, social_uow):
        ana = await world.user()
        bea = await world.user()
        competition, _, _ = await _torneo(
            world,
            {ana: tarjeta(), bea: tarjeta(h4=3)},
            estados={bea: EstadoDeTarjeta.RETIRADO},
        )

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert await _tipos(social_uow, bea) == []
        assert T.FIRST_TOURNAMENT in await _tipos(social_uow, ana)

    async def test_an_unvalidated_birdie_does_not_count(self, world, social_uow):
        """El birdie que el marcador no firma deja la tarjeta con un hueco: no hay vuelta."""
        ana = await world.user()
        golpes = tarjeta()
        del golpes[4]
        competition, _, _ = await _torneo(world, {ana: golpes}, sin_validar={ana: {4: 3}})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert await _tipos(social_uow, ana) == []

    async def test_a_group_still_on_the_course_does_not_count(self, world, social_uow):
        ana = await world.user()
        competition, _, _ = await _torneo(
            world, {ana: tarjeta(h4=3)}, estado=EstadoPartida.IN_PROGRESS
        )

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert await _tipos(social_uow, ana) == []

    async def test_a_tournament_not_completed_publishes_nothing(self, world, social_uow):
        ana = await world.user()
        competition = await world.competition(ana, enrolled=[ana], completed=False)
        course = await world.course(ana)
        round_ = await world.round(competition, course)
        await world.group(competition, round_, {ana: tarjeta(h4=3)})

        assert await _publisher(world, social_uow).execute(str(competition.id.value)) == 0


# ==================== L9: el primer torneo mira el stroke play ====================


class TestFirstTournamentLooksAtStrokePlay:
    async def test_a_previous_stroke_play_tournament_is_not_the_first(self, world, social_uow):
        ana = await world.user()
        await _torneo(world, {ana: tarjeta()})
        competition, _, _ = await _torneo(world, {ana: tarjeta()}, dia=DIA + timedelta(days=30))

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.FIRST_TOURNAMENT not in await _tipos(social_uow, ana)

    async def test_a_no_show_in_a_previous_tournament_did_not_play_it(self, world, social_uow):
        ana = await world.user()
        bea = await world.user()
        await _torneo(
            world, {bea: tarjeta(), ana: tarjeta()}, estados={ana: EstadoDeTarjeta.NO_PRESENTADO}
        )
        competition, _, _ = await _torneo(world, {ana: tarjeta()}, dia=DIA + timedelta(days=30))

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert T.FIRST_TOURNAMENT in await _tipos(social_uow, ana)


# ==================== L12: idempotencia y visibilidad ====================


class TestPublisherRules:
    async def test_closing_twice_does_not_duplicate(self, world, social_uow):
        ana = await world.user()
        competition, _, _ = await _torneo(world, {ana: tarjeta(h4=3)})
        publisher = _publisher(world, social_uow)

        await publisher.execute(str(competition.id.value))
        primera = await _tipos(social_uow, ana)
        await publisher.execute(str(competition.id.value))

        assert await _tipos(social_uow, ana) == primera

    async def test_sharing_off_publishes_only_for_him(self, world, social_uow):
        ana = await world.user(share_activity=False)
        competition, _, _ = await _torneo(world, {ana: tarjeta(h4=3)})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        eventos = await _feed(social_uow, ana)
        assert eventos
        assert all(not e.visible_to_friends for e in eventos)

    async def test_an_unknown_tournament_does_not_break(self, world, social_uow):
        assert await _publisher(world, social_uow).execute(str(uuid4())) == 0


# ==================== L12: al reabrir se retira y se vuelve a publicar ====================


class TestReopening:
    async def _reabrir(self, world, social_uow, competition) -> None:
        competition.revert_to_in_progress()
        await world.save_competition(competition)
        await PublishCompetitionNoticesUseCase(social_uow, world.users).reopened(
            str(competition.id.value)
        )

    async def test_reopening_withdraws_the_group_achievements(self, world, social_uow):
        ana = await world.user()
        competition, _, _ = await _torneo(world, {ana: tarjeta(h4=3)})
        await _publisher(world, social_uow).execute(str(competition.id.value))

        await self._reabrir(world, social_uow, competition)

        assert await _tipos(social_uow, ana) == []

    async def test_reopening_leaves_other_tournaments_alone(self, world, social_uow):
        ana = await world.user()
        otro, _, _ = await _torneo(world, {ana: tarjeta(h4=3)})
        competition, _, _ = await _torneo(world, {ana: tarjeta(h5=3)})
        publisher = _publisher(world, social_uow)
        await publisher.execute(str(otro.id.value))
        await publisher.execute(str(competition.id.value))

        await self._reabrir(world, social_uow, competition)

        birdies = [e for e in await _feed(social_uow, ana) if e.type == T.BIRDIE]
        assert [e.payload["competition_id"] for e in birdies] == [str(otro.id.value)]

    async def test_closing_again_publishes_the_corrected_card(self, world, social_uow):
        """El birdie que se corrige al reabrir no se queda colgado en el feed."""
        ana = await world.user()
        competition, _, partida = await _torneo(world, {ana: tarjeta(h4=3)})
        publisher = _publisher(world, social_uow)
        await publisher.execute(str(competition.id.value))
        await self._reabrir(world, social_uow, competition)

        async with world.comp:
            golpes = await world.comp.golpes_de_partida.de_la_partida(partida.id)
            corregido = next(g for g in golpes if g.hoyo == 4)
            corregido.anotar_propio(4, True, ana.id, MOMENTO)
            corregido.anotar_del_marcador(4, True, ana.id, MOMENTO)
            await world.comp.golpes_de_partida.guardar(corregido)
        competition.complete()
        await world.save_competition(competition)
        await publisher.execute(str(competition.id.value))

        tipos = await _tipos(social_uow, ana)
        assert T.BIRDIE not in tipos
        assert T.FIRST_TOURNAMENT in tipos


# ==================== L10 + L7: la mejor marca, de punta a punta ====================


class TestPersonalBestEndToEnd:
    """
    Cerrar el torneo con las piezas de verdad: la marca previa sale de las
    estadisticas antes de cerrar y la nueva despues. Las tarjetas de stroke play
    tienen que contar en las estadisticas, y solo desde el cierre, para que el
    record salga.
    """

    async def test_closing_a_better_stroke_play_round_publishes_the_record(self, world, social_uow):
        ana = await world.user()
        await _torneo(world, {ana: tarjeta(par=5)})
        competition = await world.competition(ana, enrolled=[ana], completed=False)
        course = await world.course(ana)
        round_ = await world.round(competition, course, DIA + timedelta(days=30))
        partida = await world.group(competition, round_, {ana: tarjeta()})

        stats = GetPlayerStatsUseCase(
            user_uow=world.users,
            competition_uow=world.comp,
            quick_match_uow=InMemoryQuickMatchUnitOfWork(),
            golf_course_uow=world.golf,
        )
        differentials = StatsPlayerDifferentialsAdapter(stats)
        publisher = TournamentAchievementsPublisher(
            _publisher(world, social_uow, differentials=differentials)
        )

        await CompleteCompetitionUseCase(world.comp, achievements=publisher).execute(
            CompleteCompetitionRequestDTO(competition_id=competition.id.value), ana.id
        )

        record = next(e for e in await _feed(social_uow, ana) if e.type == T.PERSONAL_BEST)
        assert record.source_match_id == str(partida.id.value)
        assert record.payload["kind"] == "TEE_GROUP"


# ==================== player_ids: quien jugo puede ir a la tarjeta ====================


class TestPlayerIdsOfTheGroup:
    """
    Agustín, 22 oct 2026: quien JUGÓ el grupo de un logro de torneo de otro
    puede ir a su tarjeta. El payload lleva `player_ids`: todos los del grupo,
    también el autor, ordenados para que salga siempre igual.
    """

    async def test_every_achievement_carries_the_players_of_its_group(self, world, social_uow):
        ana, bea, cris = [await world.user() for _ in range(3)]
        competition, _, _ = await _torneo(
            world, {ana: tarjeta(h4=3), bea: tarjeta(), cris: tarjeta()}
        )

        await _publisher(world, social_uow).execute(str(competition.id.value))

        esperado = sorted(str(u.id.value) for u in (ana, bea, cris))
        eventos = await _feed(social_uow, ana)
        assert eventos
        assert all(e.payload["player_ids"] == esperado for e in eventos)

    async def test_the_players_of_another_group_are_not_there(self, world, social_uow):
        ana, bea, otro = [await world.user() for _ in range(3)]
        competition = await world.competition(ana, enrolled=[ana, bea, otro])
        course = await world.course(ana)
        round_ = await world.round(competition, course)
        await world.group(competition, round_, {ana: tarjeta(h4=3), bea: tarjeta()}, numero=1)
        await world.group(competition, round_, {otro: tarjeta()}, numero=2)

        await _publisher(world, social_uow).execute(str(competition.id.value))

        birdie = next(e for e in await _feed(social_uow, ana) if e.type == T.BIRDIE)
        assert birdie.payload["player_ids"] == sorted(str(u.id.value) for u in (ana, bea))
