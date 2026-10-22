"""
Logros exclusivos por fecha real (decision de Agustin, 22 oct 2026).

«Campo nuevo» es SIEMPRE de la vuelta mas antigua del jugador en ese campo,
sea de torneo o partida rapida; «primer torneo», SIEMPRE del torneo mas
antiguo. Al publicar uno, si ya hay uno publicado anterior no sale; si los que
hay son posteriores, se retiran. Asi el estado final no depende del orden de
cierre, del dia ni del origen.

Cada escena se prueba en todos los ordenes posibles: el estado final tiene que
ser exactamente uno, en el mas antiguo.
"""

from datetime import date, datetime, timedelta
from itertools import permutations
from uuid import UUID

import pytest

from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
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
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.unit.modules.social.stroke_play_world import DIA, PAR, StrokePlayWorld, tarjeta

pytestmark = pytest.mark.asyncio

T = ActivityEventType
EXCLUSIVOS = (T.NEW_COURSE, T.FIRST_TOURNAMENT)
MADRID = "Europe/Madrid"  # en junio, UTC+2: la manana abre a las 4:00 UTC, la tarde a las 10:00
MANANA = SessionType.MORNING
TARDE = SessionType.AFTERNOON
AYER = DIA - timedelta(days=1)


def _a_las(dia: date, hora: int) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora)


class Escena:
    """Un jugador, un campo con zona y las piezas de verdad: historial, estadisticas y feed."""

    def __init__(self):
        self.social = InMemorySocialUnitOfWork()
        self.qm = InMemoryQuickMatchUnitOfWork()
        self.world = StrokePlayWorld(
            InMemoryCompetitionUnitOfWork(),
            InMemoryGolfCourseUnitOfWork(),
            InMemoryUserUnitOfWork(),
        )

    async def montar(self, timezone: str | None = MADRID):
        self.ana = await self.world.user()
        self.course = await self.world.course(self.ana, timezone=timezone)
        return self

    # --- piezas ---

    def _history(self):
        return PlayerCourseHistoryAdapter(self.qm, self.world.comp)

    def _differentials(self):
        return StatsPlayerDifferentialsAdapter(
            GetPlayerStatsUseCase(
                user_uow=self.world.users,
                competition_uow=self.world.comp,
                quick_match_uow=self.qm,
                golf_course_uow=self.world.golf,
            )
        )

    def torneos(self) -> PublishTournamentAchievementsUseCase:
        return PublishTournamentAchievementsUseCase(
            social_uow=self.social,
            competition_uow=self.world.comp,
            golf_course_uow=self.world.golf,
            user_uow=self.world.users,
            differentials=self._differentials(),
            history=self._history(),
        )

    def rapidas(self) -> PublishRoundAchievementsUseCase:
        return PublishRoundAchievementsUseCase(
            social_uow=self.social,
            quick_match_uow=self.qm,
            golf_course_uow=self.world.golf,
            user_uow=self.world.users,
            differentials=self._differentials(),
            history=self._history(),
        )

    def actividad(self) -> CompetitionActivityPublisher:
        return CompetitionActivityPublisher(
            PublishCompetitionNoticesUseCase(self.social, self.world.users),
            None,
            self.world.comp,
            achievements=self.torneos(),
            round_achievements=self.rapidas(),
        )

    # --- lo que se juega ---

    async def torneo(self, dia: date, sesion: SessionType = MANANA, *, inicio: date | None = None):
        """Un torneo en juego con una vuelta entregada de Ana en el campo."""
        torneo = await self.world.competition(
            self.ana, enrolled=[self.ana], completed=False, start=inicio or dia
        )
        grupo = await self.world.group(
            torneo, await self.world.round(torneo, self.course, dia, sesion), {self.ana: tarjeta()}
        )
        return torneo, grupo

    async def rapida(self, creada: datetime, course=None) -> QuickMatch:
        """Una partida rapida terminada en el campo, creada en `creada` (UTC sin zona)."""
        nueva = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=self.ana.id,
            golf_course_id=(course or self.course).id,
            scoring_format=ScoringFormat.MEDAL,
            creator_tee_color=TeeColor.YELLOW,
            creator_tee_gender=Gender.MALE,
        )
        participante = nueva.participants[0].participant_id
        nueva.start(scorer_ids=[participante])
        nueva.complete()
        partida = QuickMatch.reconstruct(
            id=nueva.id,
            creator_id=nueva.creator_id,
            golf_course_id=nueva.golf_course_id,
            match_format=nueva.match_format,
            status=nueva.status,
            participants=list(nueva.participants),
            scoring_format=nueva.scoring_format,
            allowance_percentage=nueva.allowance_percentage,
            play_mode=nueva.play_mode,
            scorer_ids=list(nueva.scorer_ids),
            created_at=creada,
            updated_at=creada,
        )
        async with self.qm:
            await self.qm.quick_matches.add(partida)
            for hoyo in range(1, 19):
                await self.qm.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=partida.id,
                        hole_number=hoyo,
                        participant_id=participante,
                        score=PAR,
                        recorded_by_participant_id=participante,
                    )
                )
        return partida

    # --- lo que pasa ---

    async def cerrar(self, torneo) -> None:
        torneo.complete()
        await self.world.save_competition(torneo)
        await TournamentAchievementsPublisher(self.torneos()).publish(str(torneo.id.value))

    async def reabrir(self, torneo) -> None:
        torneo.revert_to_in_progress()
        await self.world.save_competition(torneo)
        await self.actividad().reopened(torneo.id)

    async def cancelar(self, torneo) -> None:
        torneo.cancel()
        await self.world.save_competition(torneo)
        await self.actividad().cancelled(torneo.id)

    async def publicar_rapida(self, partida: QuickMatch) -> None:
        await self.rapidas().execute(str(partida.id.value))

    # --- lo que queda ---

    async def eventos(self, tipo: ActivityEventType) -> list[ActivityEvent]:
        async with self.social:
            return [
                e
                for e in await self.social.activity_events.find_in(
                    [ActivitySlice(user_ids=(self.ana.id,), types=frozenset({tipo}))], limit=100
                )
                if e.type == tipo
            ]

    async def de(self, tipo: ActivityEventType) -> list[str]:
        """De donde cuelga cada logro de ese tipo: el origen (partido, grupo o partida rapida)."""
        return sorted(e.source_match_id for e in await self.eventos(tipo))


async def _escena(timezone: str | None = MADRID) -> Escena:
    return await Escena().montar(timezone)


def _id(cosa) -> str:
    return str(cosa.id.value)


# ==================== 1. Partida rapida frente a torneo ====================


class TestQuickMatchAgainstTournament:
    """
    Caso 1 del probador: una partida rapida completada antes de que se cierre
    un torneo jugado esa misma manana en el campo. En cualquier orden, el
    campo nuevo es de lo que se jugo antes.
    """

    @pytest.mark.parametrize("rapida_primero", [True, False])
    async def test_the_morning_round_beats_a_later_quick_match_the_same_day(self, rapida_primero):
        e = await _escena()
        torneo, grupo = await e.torneo(DIA, MANANA)  # 4:00 UTC
        partida = await e.rapida(_a_las(DIA, 9))

        if rapida_primero:
            await e.publicar_rapida(partida)
            await e.cerrar(torneo)
        else:
            await e.cerrar(torneo)
            await e.publicar_rapida(partida)

        assert await e.de(T.NEW_COURSE) == [_id(grupo)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    @pytest.mark.parametrize("rapida_primero", [True, False])
    async def test_a_quick_match_before_the_round_keeps_it(self, rapida_primero):
        e = await _escena()
        torneo, grupo = await e.torneo(DIA, TARDE)  # 10:00 UTC
        partida = await e.rapida(_a_las(DIA, 7))

        if rapida_primero:
            await e.publicar_rapida(partida)
            await e.cerrar(torneo)
        else:
            await e.cerrar(torneo)
            await e.publicar_rapida(partida)

        assert await e.de(T.NEW_COURSE) == [_id(partida)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    @pytest.mark.parametrize("rapida_primero", [True, False])
    async def test_a_tournament_the_day_before_beats_a_quick_match(self, rapida_primero):
        e = await _escena()
        torneo, grupo = await e.torneo(AYER, TARDE)
        partida = await e.rapida(_a_las(DIA, 7))

        if rapida_primero:
            await e.publicar_rapida(partida)
            await e.cerrar(torneo)
        else:
            await e.cerrar(torneo)
            await e.publicar_rapida(partida)

        assert await e.de(T.NEW_COURSE) == [_id(grupo)]

    @pytest.mark.parametrize("rapida_primero", [True, False])
    async def test_a_quick_match_the_day_before_beats_a_tournament(self, rapida_primero):
        e = await _escena()
        torneo, _ = await e.torneo(DIA, MANANA)
        partida = await e.rapida(_a_las(AYER, 20))

        if rapida_primero:
            await e.publicar_rapida(partida)
            await e.cerrar(torneo)
        else:
            await e.cerrar(torneo)
            await e.publicar_rapida(partida)

        assert await e.de(T.NEW_COURSE) == [_id(partida)]

    async def test_two_quick_matches_closed_in_reverse_order(self):
        """Tambien entre partidas rapidas: la que se creo antes, aunque se publique despues."""
        e = await _escena()
        antes = await e.rapida(_a_las(DIA, 7))
        despues = await e.rapida(_a_las(DIA, 9))

        await e.publicar_rapida(despues)
        await e.publicar_rapida(antes)

        assert await e.de(T.NEW_COURSE) == [_id(antes)]


# ==================== 2. Dos torneos en la misma sesion ====================


class TestTwoTournamentsInTheSameSession:
    """
    Caso 2 del probador: dos torneos del mismo dia, en la misma sesion y el
    mismo campo. Mismo instante: desempata el id del torneo, el mismo para
    los dos logros.
    """

    @pytest.mark.parametrize("orden", [(0, 1), (1, 0)])
    async def test_one_of_each_in_the_lower_id(self, orden):
        e = await _escena()
        uno = await e.torneo(DIA, MANANA)
        otro = await e.torneo(DIA, MANANA)
        torneos = [uno, otro]

        for i in orden:
            await e.cerrar(torneos[i][0])

        menor = min(torneos, key=lambda t: _id(t[0]))
        assert await e.de(T.NEW_COURSE) == [_id(menor[1])]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(menor[1])]

    async def test_the_same_session_is_decided_by_the_tournament_not_the_group(self, monkeypatch):
        """
        El grupo del torneo de id MAYOR tiene el id MENOR: si «campo nuevo»
        desempatara por el grupo, cada logro acabaria en un torneo distinto.
        """
        e = await _escena()
        menor = await e.world.competition(e.ana, enrolled=[e.ana], completed=False)
        mayor = await e.world.competition(e.ana, enrolled=[e.ana], completed=False)
        menor, mayor = sorted((menor, mayor), key=_id)
        ids_grupo = iter([PartidaId(UUID(int=1)), PartidaId(UUID(int=2))])
        monkeypatch.setattr(PartidaId, "generate", classmethod(lambda cls: next(ids_grupo)))
        grupo_del_mayor = await e.world.group(
            mayor, await e.world.round(mayor, e.course, DIA, MANANA), {e.ana: tarjeta()}
        )
        grupo_del_menor = await e.world.group(
            menor, await e.world.round(menor, e.course, DIA, MANANA), {e.ana: tarjeta()}
        )
        assert _id(grupo_del_mayor) < _id(grupo_del_menor)

        await e.cerrar(mayor)
        await e.cerrar(menor)

        assert await e.de(T.NEW_COURSE) == [_id(grupo_del_menor)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo_del_menor)]


# ==================== 3. Dias distintos, cerrados al reves ====================


class TestDifferentDaysClosedInReverse:
    """Caso 3 del probador: el de hoy se cierra antes que el de ayer."""

    @pytest.mark.parametrize("orden", [(0, 1), (1, 0)])
    async def test_yesterday_keeps_both(self, orden):
        e = await _escena()
        ayer = await e.torneo(AYER, TARDE)
        hoy = await e.torneo(DIA, MANANA)
        torneos = [ayer, hoy]

        for i in orden:
            await e.cerrar(torneos[i][0])

        assert await e.de(T.NEW_COURSE) == [_id(ayer[1])]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(ayer[1])]

    async def test_three_tournaments_and_a_quick_match_in_every_order(self):
        """Todas las permutaciones: siempre uno, en el mas antiguo."""
        for orden in permutations(range(4)):
            e = await _escena()
            antier = DIA - timedelta(days=2)
            primero = await e.torneo(antier, TARDE)
            segundo = await e.torneo(AYER, MANANA)
            tercero = await e.torneo(DIA, MANANA)
            partida = await e.rapida(_a_las(DIA, 9))
            pasos = [
                (e.cerrar, primero[0]),
                (e.cerrar, segundo[0]),
                (e.cerrar, tercero[0]),
                (e.publicar_rapida, partida),
            ]

            for i in orden:
                paso, que = pasos[i]
                await paso(que)

            assert await e.de(T.NEW_COURSE) == [_id(primero[1])], orden
            assert await e.de(T.FIRST_TOURNAMENT) == [_id(primero[1])], orden

    async def test_the_first_round_played_decides_not_the_start_date(self):
        """El instante de la primera vuelta, no el dia de inicio del torneo."""
        e = await _escena()
        # Empieza antes, pero Ana no juega hasta la tarde de DIA
        tardio = await e.torneo(DIA, TARDE, inicio=AYER)
        temprano = await e.torneo(DIA, MANANA)

        await e.cerrar(tardio[0])
        await e.cerrar(temprano[0])

        assert await e.de(T.FIRST_TOURNAMENT) == [_id(temprano[1])]


# ==================== 4. Cancelar el anterior ====================


class TestCancellingTheEarlierOne:
    """Lo que sigue abierto no cuenta; si se cancela, el posterior se queda el logro."""

    async def test_the_later_tournament_keeps_both_when_the_earlier_is_cancelled(self):
        e = await _escena()
        anterior, _ = await e.torneo(DIA, MANANA)
        posterior, grupo = await e.torneo(DIA, TARDE)

        await e.cerrar(posterior)
        assert await e.de(T.NEW_COURSE) == [_id(grupo)]
        await e.cancelar(anterior)

        assert await e.de(T.NEW_COURSE) == [_id(grupo)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    async def test_a_quick_match_keeps_it_when_the_earlier_tournament_is_cancelled(self):
        e = await _escena()
        anterior, _ = await e.torneo(DIA, MANANA)
        partida = await e.rapida(_a_las(DIA, 9))

        await e.publicar_rapida(partida)
        await e.cancelar(anterior)

        assert await e.de(T.NEW_COURSE) == [_id(partida)]
        assert await e.de(T.FIRST_TOURNAMENT) == []


# ==================== 5. Reabrir el anterior ====================


class TestReopeningTheEarlierOne:
    """
    Reabrir retira sus logros y los hereda el siguiente mas antiguo ya
    publicable; volver a cerrarlo se los lleva otra vez.
    """

    async def test_the_later_tournament_inherits_and_gives_them_back(self):
        e = await _escena()
        anterior, grupo_anterior = await e.torneo(AYER, TARDE)
        posterior, grupo_posterior = await e.torneo(DIA, MANANA)
        await e.cerrar(posterior)
        await e.cerrar(anterior)

        await e.reabrir(anterior)
        assert await e.de(T.NEW_COURSE) == [_id(grupo_posterior)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo_posterior)]

        await e.cerrar(anterior)
        assert await e.de(T.NEW_COURSE) == [_id(grupo_anterior)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo_anterior)]

    async def test_a_quick_match_inherits_the_new_course(self):
        e = await _escena()
        anterior, grupo = await e.torneo(DIA, MANANA)
        partida = await e.rapida(_a_las(DIA, 9))
        await e.cerrar(anterior)
        await e.publicar_rapida(partida)
        assert await e.de(T.NEW_COURSE) == [_id(grupo)]

        await e.reabrir(anterior)
        assert await e.de(T.NEW_COURSE) == [_id(partida)]
        assert await e.de(T.FIRST_TOURNAMENT) == []

        await e.cerrar(anterior)
        assert await e.de(T.NEW_COURSE) == [_id(grupo)]

    async def test_the_first_tournament_is_inherited_in_another_course(self):
        """El heredero de «primer torneo» no tiene por que haber jugado en el mismo campo."""
        e = await _escena()
        anterior, _ = await e.torneo(AYER, TARDE)
        e.course = await e.world.course(e.ana, timezone=MADRID)
        posterior, grupo = await e.torneo(DIA, MANANA)
        await e.cerrar(anterior)
        await e.cerrar(posterior)
        assert await e.de(T.FIRST_TOURNAMENT) != [_id(grupo)]

        await e.reabrir(anterior)

        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    async def test_a_quick_match_inherits_only_its_new_course(self):
        """Heredar no vuelve a publicar el resto de sus logros."""
        e = await _escena()
        partida = await e.rapida(_a_las(DIA, 9))
        async with e.qm:
            golpes = await e.qm.quick_match_hole_scores.find_by_match(partida.id)
            golpes[0].update_score(PAR - 1, golpes[0].recorded_by_participant_id)
            await e.qm.quick_match_hole_scores.update(golpes[0])

        await e.rapidas().republish_new_course(_id(partida))

        assert [x.type for x in await e.eventos(T.NEW_COURSE)] == [T.NEW_COURSE]
        assert await e.eventos(T.BIRDIE) == []

    async def test_reopening_and_cancelling_leaves_them_in_the_later_one(self):
        e = await _escena()
        anterior, _ = await e.torneo(AYER, TARDE)
        posterior, grupo = await e.torneo(DIA, MANANA)
        await e.cerrar(anterior)
        await e.cerrar(posterior)

        await e.reabrir(anterior)
        await e.cancelar(anterior)

        assert await e.de(T.NEW_COURSE) == [_id(grupo)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    async def test_reopening_the_later_one_changes_nothing(self):
        e = await _escena()
        anterior, grupo = await e.torneo(AYER, TARDE)
        posterior, _ = await e.torneo(DIA, MANANA)
        await e.cerrar(anterior)
        await e.cerrar(posterior)

        await e.reabrir(posterior)
        await e.cerrar(posterior)

        assert await e.de(T.NEW_COURSE) == [_id(grupo)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    async def test_interleaved_reopenings(self):
        e = await _escena()
        anterior, grupo_anterior = await e.torneo(DIA, MANANA)
        posterior, grupo_posterior = await e.torneo(DIA, TARDE)
        await e.cerrar(anterior)
        await e.cerrar(posterior)

        await e.reabrir(anterior)
        await e.reabrir(posterior)
        assert await e.de(T.NEW_COURSE) == []
        await e.cerrar(posterior)
        assert await e.de(T.NEW_COURSE) == [_id(grupo_posterior)]
        await e.cerrar(anterior)

        assert await e.de(T.NEW_COURSE) == [_id(grupo_anterior)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo_anterior)]

    async def test_a_failing_inheritance_does_not_break_the_reopening(self, monkeypatch):
        e = await _escena()
        anterior, _ = await e.torneo(AYER, TARDE)
        posterior, _ = await e.torneo(DIA, MANANA)
        await e.cerrar(anterior)
        await e.cerrar(posterior)

        async def _rompe(self, *args, **kwargs):
            raise RuntimeError("feed caido")

        monkeypatch.setattr(PublishTournamentAchievementsUseCase, "heirs_of", _rompe)

        await e.reabrir(anterior)

        assert await e.de(T.NEW_COURSE) == []

    async def test_one_failing_heir_does_not_stop_the_others(self, monkeypatch):
        e = await _escena()
        anterior, _ = await e.torneo(AYER, TARDE)
        posterior, grupo = await e.torneo(DIA, MANANA)
        # Otro campo del torneo anterior, jugado despues en una partida rapida:
        # heredarlo falla, y aun asi el torneo posterior hereda lo suyo
        otro_campo = await e.world.course(e.ana, timezone=MADRID)
        await e.world.group(
            anterior,
            await e.world.round(anterior, otro_campo, AYER, TARDE),
            {e.ana: tarjeta()},
            numero=2,
        )
        partida = await e.rapida(_a_las(DIA, 20), otro_campo)
        await e.cerrar(anterior)
        await e.cerrar(posterior)
        await e.publicar_rapida(partida)

        async def _rompe(self, *args, **kwargs):
            raise RuntimeError("feed caido")

        monkeypatch.setattr(PublishRoundAchievementsUseCase, "execute", _rompe)

        await e.reabrir(anterior)

        assert await e.de(T.NEW_COURSE) == [_id(grupo)]
        assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo)]

    @pytest.mark.parametrize("rompe_el_menor", [True, False])
    async def test_one_failing_tournament_heir_does_not_stop_the_other(
        self, monkeypatch, rompe_el_menor
    ):
        e = await _escena()
        campo_1 = e.course
        campo_2 = await e.world.course(e.ana, timezone=MADRID)
        anterior, _ = await e.torneo(AYER, TARDE)
        await e.world.group(
            anterior,
            await e.world.round(anterior, campo_2, AYER, TARDE),
            {e.ana: tarjeta()},
            numero=2,
        )
        posterior, grupo_posterior = await e.torneo(DIA, MANANA)
        e.course = campo_2
        otro, grupo_otro = await e.torneo(DIA, TARDE)
        e.course = campo_1
        for torneo in (anterior, posterior, otro):
            await e.cerrar(torneo)
        roto = min(_id(posterior), _id(otro)) if rompe_el_menor else max(_id(posterior), _id(otro))
        original = PublishTournamentAchievementsUseCase.execute

        async def _uno_roto(self, competition_id_raw):
            if competition_id_raw == roto:
                raise RuntimeError("feed caido")
            return await original(self, competition_id_raw)

        monkeypatch.setattr(PublishTournamentAchievementsUseCase, "execute", _uno_roto)

        await e.reabrir(anterior)

        nuevos = await e.de(T.NEW_COURSE)
        if roto == _id(posterior):
            assert nuevos == [_id(grupo_otro)]
        else:
            assert nuevos == [_id(grupo_posterior)]
            assert await e.de(T.FIRST_TOURNAMENT) == [_id(grupo_posterior)]


# ==================== 6. La papelera del autor ====================


class TestTheAuthorsTrash:
    """
    La papelera no cambia de quien es el logro: se filtra al leer. Una partida
    rapida en la papelera que se jugo antes sigue siendo la mas antigua.
    """

    @pytest.mark.parametrize("rapida_primero", [True, False])
    async def test_a_trashed_earlier_quick_match_still_holds_it(self, rapida_primero):
        e = await _escena()
        partida = await e.rapida(_a_las(DIA, 2))
        partida.hide_for(partida.participants[0].participant_id)
        async with e.qm:
            await e.qm.quick_matches.update(partida)
        torneo, _ = await e.torneo(DIA, TARDE)

        if rapida_primero:
            await e.publicar_rapida(partida)
            await e.cerrar(torneo)
        else:
            await e.cerrar(torneo)
            await e.publicar_rapida(partida)

        assert await e.de(T.NEW_COURSE) == [_id(partida)]

    async def test_the_author_still_sees_it_and_friends_do_not(self):
        e = await _escena()
        partida = await e.rapida(_a_las(DIA, 2))
        await e.publicar_rapida(partida)
        e.social.activity_events.trashed_quick_matches.add((_id(partida), e.ana.id))
        amigo = await e.world.user()

        async with e.social:
            propios = await e.social.activity_events.count_in(
                [ActivitySlice(user_ids=(e.ana.id,), types=frozenset({T.NEW_COURSE}))],
                since=None,
                hide_trashed_quick_matches_from=e.ana.id,
            )
            ajenos = await e.social.activity_events.count_in(
                [ActivitySlice(user_ids=(e.ana.id,), types=frozenset({T.NEW_COURSE}))],
                since=None,
                hide_trashed_quick_matches_from=amigo.id,
            )
        assert (propios, ajenos) == (1, 0)


# ==================== 7. El payload y lo ya publicado ====================


class TestPayloadAndWhatIsPublished:
    async def test_both_carry_the_instant_in_utc(self):
        e = await _escena()
        torneo, grupo = await e.torneo(DIA, TARDE)
        await e.cerrar(torneo)

        for tipo in EXCLUSIVOS:
            (evento,) = await e.eventos(tipo)
            assert evento.payload["played_at"] == "2026-06-01T10:00:00Z"
            # El contrato de antes sigue ahi
            assert evento.payload["competition_id"] == _id(torneo)
            assert evento.payload["kind"] == "TEE_GROUP"
            assert evento.payload["group_id"] == _id(grupo)
            assert evento.payload["player_ids"] == [_id(e.ana)]

    async def test_a_quick_match_carries_its_creation_instant(self):
        e = await _escena()
        partida = await e.rapida(datetime(2026, 6, 1, 7, 30, 15))
        await e.publicar_rapida(partida)

        (evento,) = await e.eventos(T.NEW_COURSE)
        assert evento.payload["played_at"] == "2026-06-01T07:30:15Z"

    async def test_without_a_zone_the_session_hour_is_taken_as_utc(self):
        """Decision de este arreglo: sin zona, el dia y la hora local de la sesion, como UTC."""
        e = await _escena(timezone=None)
        torneo, _ = await e.torneo(DIA, TARDE)
        await e.cerrar(torneo)

        (evento,) = await e.eventos(T.NEW_COURSE)
        assert evento.payload["played_at"] == "2026-06-01T12:00:00Z"

    async def test_the_first_tournament_is_dated_by_the_first_round_played(self):
        e = await _escena()
        torneo, _ = await e.torneo(DIA, TARDE)
        await e.world.group(
            torneo, await e.world.round(torneo, e.course, AYER, MANANA), {e.ana: tarjeta()}
        )
        await e.cerrar(torneo)

        (evento,) = await e.eventos(T.FIRST_TOURNAMENT)
        assert evento.payload["played_at"] == "2026-05-31T04:00:00Z"

    async def test_a_withdrawn_first_round_dates_the_first_tournament(self):
        """Se retiro en su primera vuelta: el torneo empezo ahi, aunque el logro cuelgue de otra."""
        e = await _escena()
        torneo, grupo = await e.torneo(DIA, TARDE)
        await e.world.group(
            torneo,
            await e.world.round(torneo, e.course, AYER, MANANA),
            {e.ana: tarjeta()},
            estados={e.ana: EstadoDeTarjeta.RETIRADO},
        )
        await e.cerrar(torneo)

        (evento,) = await e.eventos(T.FIRST_TOURNAMENT)
        assert evento.source_match_id == _id(grupo)
        assert evento.payload["played_at"] == "2026-05-31T04:00:00Z"

    async def test_republishing_keeps_the_same_event(self):
        """Idempotente: lo que ya estaba igual conserva su id y su fecha."""
        e = await _escena()
        torneo, _ = await e.torneo(DIA, MANANA)
        partida = await e.rapida(_a_las(AYER, 9))
        await e.publicar_rapida(partida)
        await e.cerrar(torneo)
        antes = [(x.id, x.published_at) for t in EXCLUSIVOS for x in await e.eventos(t)]

        await e.publicar_rapida(partida)
        await TournamentAchievementsPublisher(e.torneos()).publish(_id(torneo))

        assert [(x.id, x.published_at) for t in EXCLUSIVOS for x in await e.eventos(t)] == antes

    async def test_a_legacy_double_without_instant_is_cleaned(self):
        """
        Un logro publicado antes de llevar `played_at` se compara por su
        `occurred_at`; el posterior que sobra se retira.
        """
        e = await _escena()
        partida = await e.rapida(_a_las(DIA, 9))
        viejo = ActivityEvent.create(
            user_id=e.ana.id,
            type=T.NEW_COURSE,
            occurred_at=_a_las(DIA, 20),
            source_match_id="vieja-partida",
            payload={"golf_course_id": str(e.course.id.value), "holes_played": 18},
        )
        async with e.social:
            await e.social.activity_events.add_many([viejo])

        await e.publicar_rapida(partida)

        assert await e.de(T.NEW_COURSE) == [_id(partida)]

    async def test_another_course_is_another_new_course(self):
        e = await _escena()
        partida = await e.rapida(_a_las(DIA, 7))
        e.course = await e.world.course(e.ana, timezone=MADRID)
        torneo, grupo = await e.torneo(DIA, TARDE)

        await e.publicar_rapida(partida)
        await e.cerrar(torneo)

        assert await e.de(T.NEW_COURSE) == sorted([_id(partida), _id(grupo)])


# ==================== 8. El candado ====================


class TestLocks:
    """
    Comprobar y retirar, bajo candado por jugador: siempre despues del del
    torneo y en orden, para que torneos y partidas rapidas no se crucen.
    """

    async def test_a_tournament_locks_itself_and_then_its_players_in_order(self, monkeypatch):
        e = await _escena()
        bea = await e.world.user()
        torneo = await e.world.competition(e.ana, enrolled=[e.ana, bea], completed=False)
        await e.world.group(
            torneo,
            await e.world.round(torneo, e.course, DIA, MANANA),
            {e.ana: tarjeta(), bea: tarjeta()},
        )
        candados: list[str] = []

        async def _apunta(self, scope_id):
            candados.append(scope_id)

        monkeypatch.setattr(type(e.social.activity_events), "lock_scope", _apunta)

        await e.cerrar(torneo)

        jugadores = sorted(f"player:{_id(u)}" for u in (e.ana, bea))
        assert candados == [_id(torneo), *jugadores]

    async def test_a_quick_match_locks_its_players(self, monkeypatch):
        e = await _escena()
        partida = await e.rapida(_a_las(DIA, 7))
        candados: list[str] = []

        async def _apunta(self, scope_id):
            candados.append(scope_id)

        monkeypatch.setattr(type(e.social.activity_events), "lock_scope", _apunta)

        await e.publicar_rapida(partida)

        assert candados == [f"player:{_id(e.ana)}"]
