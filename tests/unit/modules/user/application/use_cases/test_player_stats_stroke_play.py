"""
Las estadisticas del perfil cuentan las tarjetas de stroke play de torneo (L10,
tabla del 22 oct 2026): vueltas jugadas, media y diferencial.

Sin ellas, la «mejor marca» de un torneo stroke play no saldria nunca: el
record se mide con el mejor diferencial de estas mismas estadisticas.

Cuenta la tarjeta ENTREGADA de un grupo acabado, con los hoyos validados, de
un torneo ya cerrado. El cierre es lo que hace que la marca previa (que se
toma justo antes de cerrar) no la incluya y la de despues si.
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.social.stroke_play_world import StrokePlayWorld, tarjeta
from tests.unit.modules.user.application.use_cases.test_get_player_stats_use_case import (
    _Consultas,
)

pytestmark = pytest.mark.asyncio

# Barra amarilla: CR 70, slope 125; par 72. Indice 10 al 100 %:
# 10 x 125 / 113 + (70 - 72) = 9,06 -> 9 golpes. Todo al par: 72 brutos.
NET_TO_PAR_ALL_PARS = -9
# (113 / 125) x (72 - 70) = 1,81 -> 1,8
DIFFERENTIAL_ALL_PARS = 1.8


@pytest.fixture
def world():
    return StrokePlayWorld(
        InMemoryCompetitionUnitOfWork(), InMemoryGolfCourseUnitOfWork(), InMemoryUserUnitOfWork()
    )


def _stats(world) -> GetPlayerStatsUseCase:
    return GetPlayerStatsUseCase(
        user_uow=world.users,
        competition_uow=world.comp,
        quick_match_uow=InMemoryQuickMatchUnitOfWork(),
        golf_course_uow=world.golf,
    )


async def _jugada(world, ana, golpes=None, *, completed=True, play_mode=PlayMode.HANDICAP, **g):
    competition = await world.competition(
        ana, enrolled=[ana], completed=completed, play_mode=play_mode
    )
    course = await world.course(ana)
    round_ = await world.round(competition, course)
    partida = await world.group(competition, round_, {ana: golpes or tarjeta()}, **g)
    return competition, course, partida


class TestStrokePlayCardsCount:
    async def test_a_handed_in_card_counts_as_a_round(self, world):
        ana = await world.user()
        await _jugada(world, ana)

        stats = await _stats(world).execute(ana.id)

        assert stats.rounds_played == 1
        assert stats.scoring_avg == NET_TO_PAR_ALL_PARS
        assert stats.best_differential == pytest.approx(DIFFERENTIAL_ALL_PARS)
        assert stats.rounds_with_differential == 1

    async def test_the_index_is_the_one_fixed_in_the_group(self, world):
        """Como en la Ryder: la foto del grupo, no el hándicap de hoy en el perfil."""
        ana = await world.user(handicap=30.0)
        await _jugada(world, ana, handicap=Decimal("10"))

        stats = await _stats(world).execute(ana.id)

        assert stats.scoring_avg == NET_TO_PAR_ALL_PARS

    async def test_a_scratch_tournament_gives_no_strokes(self, world):
        ana = await world.user()
        await _jugada(world, ana, play_mode=PlayMode.SCRATCH)

        stats = await _stats(world).execute(ana.id)

        assert stats.scoring_avg == 0

    async def test_a_validated_raya_is_a_played_hole(self, world):
        ana = await world.user()
        await _jugada(world, ana, tarjeta(h4=None))

        stats = await _stats(world).execute(ana.id)

        assert stats.rounds_played == 1

    async def test_only_his_own_card_counts(self, world):
        ana = await world.user()
        bea = await world.user()
        competition = await world.competition(ana, enrolled=[ana, bea])
        course = await world.course(ana)
        round_ = await world.round(competition, course)
        await world.group(competition, round_, {ana: tarjeta(), bea: tarjeta(h1=2, h2=2)})

        stats = await _stats(world).execute(ana.id)

        assert stats.rounds_played == 1
        assert stats.scoring_avg == NET_TO_PAR_ALL_PARS

    async def test_a_partners_holes_never_fill_his_card(self, world):
        """A Ana le falta el 9: los hoyos de Bea no completan su tarjeta."""
        ana = await world.user()
        bea = await world.user()
        competition = await world.competition(ana, enrolled=[ana, bea])
        course = await world.course(ana)
        round_ = await world.round(competition, course)
        incompleta = tarjeta()
        del incompleta[9]
        await world.group(competition, round_, {ana: incompleta, bea: tarjeta()})

        assert (await _stats(world).execute(ana.id)).rounds_played == 0

    async def test_filtered_by_course(self, world):
        ana = await world.user()
        _, course, _ = await _jugada(world, ana)
        otro = await world.course(ana)

        assert (await _stats(world).execute(ana.id, course.id)).rounds_played == 1
        assert (await _stats(world).execute(ana.id, otro.id)).rounds_played == 0

    async def test_the_breakdown_sees_the_same_rounds(self, world):
        ana = await world.user()
        await _jugada(world, ana, tarjeta(h4=3))

        breakdown = await _stats(world).execute_breakdown(ana.id)

        assert breakdown.rounds_counted == 1
        assert breakdown.gross_distribution.birdie_or_better == 1


class TestStrokePlayCardsThatDoNotCount:
    async def test_a_withdrawn_card_does_not_count(self, world):
        ana = await world.user()
        bea = await world.user()
        competition = await world.competition(ana, enrolled=[ana, bea])
        course = await world.course(ana)
        round_ = await world.round(competition, course)
        await world.group(
            competition,
            round_,
            {ana: tarjeta(), bea: tarjeta()},
            estados={ana: EstadoDeTarjeta.RETIRADO},
        )

        assert (await _stats(world).execute(ana.id)).rounds_played == 0

    async def test_a_no_show_does_not_count(self, world):
        ana = await world.user()
        bea = await world.user()
        competition = await world.competition(ana, enrolled=[ana, bea])
        course = await world.course(ana)
        round_ = await world.round(competition, course)
        await world.group(
            competition,
            round_,
            {ana: tarjeta(), bea: tarjeta()},
            estados={ana: EstadoDeTarjeta.NO_PRESENTADO},
        )

        assert (await _stats(world).execute(ana.id)).rounds_played == 0

    async def test_an_unvalidated_hole_leaves_the_round_out(self, world):
        ana = await world.user()
        golpes = tarjeta()
        del golpes[9]
        await _jugada(world, ana, golpes, sin_validar={ana: {9: 4}})

        assert (await _stats(world).execute(ana.id)).rounds_played == 0

    async def test_a_tournament_not_yet_closed_does_not_count(self, world):
        ana = await world.user()
        await _jugada(world, ana, completed=False)

        assert (await _stats(world).execute(ana.id)).rounds_played == 0

    async def test_a_group_still_playing_does_not_count(self, world):
        ana = await world.user()
        await _jugada(world, ana, estado=EstadoPartida.IN_PROGRESS)

        assert (await _stats(world).execute(ana.id)).rounds_played == 0


class TestReadsInBulk:
    async def test_no_query_per_group(self, world, monkeypatch):
        """Dos grupos en dos campos: nada se lee uno a uno."""
        ana = await world.user()
        await _jugada(world, ana)
        await _jugada(world, ana)
        uno_a_uno: list = []

        def _espia(repo, metodo):
            original = getattr(repo, metodo)

            async def _llamada(*args, **kwargs):
                uno_a_uno.append(metodo)
                return await original(*args, **kwargs)

            monkeypatch.setattr(repo, metodo, _llamada)

        _espia(world.comp.rounds, "find_by_id")
        _espia(world.comp.competitions, "find_by_id")
        _espia(world.comp.golpes_de_partida, "de_la_partida")
        _espia(world.golf.golf_courses, "find_by_id")

        stats = await _stats(world).execute(ana.id)

        assert stats.rounds_played == 2
        assert uno_a_uno == []


class TestExcludingOneTournament:
    """La marca de antes de un torneo: sin ninguna de sus vueltas, Ryder o stroke play."""

    async def test_its_groups_and_matches_are_left_out(self, world):
        ana = await world.user()
        rival = await world.user()
        competition, course, _ = await _jugada(world, ana)
        ryder = await world.competition(ana, tipo=TournamentType.RYDER_CUP, enrolled=[ana, rival])
        await world.match(await world.round(ryder, course), ana, rival, tarjeta())

        todo = await _stats(world).execute(ana.id)
        sin_stroke = await _stats(world).execute(
            ana.id, excluding_competition_id=str(competition.id.value)
        )
        sin_ryder = await _stats(world).execute(
            ana.id, excluding_competition_id=str(ryder.id.value)
        )

        assert todo.rounds_played == 2
        assert sin_stroke.rounds_played == 1
        assert sin_ryder.rounds_played == 1


class TestStrokePlayCardsInBatches:
    """
    Tabla del 22 oct 2026, M, tras traer la #640: las tarjetas de stroke play
    tambien se leen por lotes, con o sin el torneo excluido. Las consultas no
    crecen con el numero de torneos.
    """

    async def _consultas(self, cuantos: int, excluir: bool) -> tuple[int, int]:
        world = StrokePlayWorld(
            InMemoryCompetitionUnitOfWork(),
            InMemoryGolfCourseUnitOfWork(),
            InMemoryUserUnitOfWork(),
        )
        ana = await world.user()
        torneos = [(await _jugada(world, ana))[0] for _ in range(cuantos)]
        qm = InMemoryQuickMatchUnitOfWork()
        consultas = _Consultas(
            user=world.users, competition=world.comp, quick_match=qm, golf_course=world.golf
        )
        caso = GetPlayerStatsUseCase(
            user_uow=world.users,
            competition_uow=world.comp,
            quick_match_uow=qm,
            golf_course_uow=world.golf,
        )
        excluido = str(torneos[0].id.value) if excluir else None

        stats = await caso.execute(ana.id, excluding_competition_id=excluido)

        return stats.rounds_played, len(consultas.llamadas)

    @pytest.mark.parametrize("excluir", [False, True])
    async def test_the_same_queries_with_two_tournaments_as_with_six(self, excluir):
        dos, con_dos = await self._consultas(2, excluir)
        seis, con_seis = await self._consultas(6, excluir)

        assert (dos, seis) == ((1, 5) if excluir else (2, 6))
        assert con_seis == con_dos
