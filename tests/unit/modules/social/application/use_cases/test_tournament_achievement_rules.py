"""
Reglas de los logros de torneo decididas por Agustin el 22 oct 2026, con las
piezas de verdad (historial de campos y estadisticas), en la Ryder y en stroke
play:

1. «Campo nuevo»: no lo habias jugado ANTES de ese torneo. Sale una vez, con la
   primera vuelta del torneo en ese campo; las demas no lo bloquean ni lo repiten.
2. «Mejor marca»: contra la marca de antes del torneo, sin ninguna de sus vueltas.
3. Reabrir una Ryder retira sus logros y cerrarla otra vez los vuelve a publicar.
4. Todo logro de torneo lleva `competition_id`.
5. Solo cuenta como jugado un torneo CERRADO, y nunca el que se esta juzgando.
6. Reabrir y publicar se serializan con el candado del torneo.
"""

from datetime import date, datetime, timedelta
from uuid import UUID

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CompleteCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.domain.value_objects.partida_id import PartidaId
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
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.unit.modules.social.stroke_play_world import DIA, StrokePlayWorld, tarjeta

pytestmark = pytest.mark.asyncio

T = ActivityEventType
RYDER = TournamentType.RYDER_CUP


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def world():
    return StrokePlayWorld(
        InMemoryCompetitionUnitOfWork(), InMemoryGolfCourseUnitOfWork(), InMemoryUserUnitOfWork()
    )


def _publisher(world, social_uow, qm_uow=None) -> PublishTournamentAchievementsUseCase:
    """El publicador con el historial y las estadisticas de verdad."""
    stats = GetPlayerStatsUseCase(
        user_uow=world.users,
        competition_uow=world.comp,
        quick_match_uow=InMemoryQuickMatchUnitOfWork(),
        golf_course_uow=world.golf,
    )
    return PublishTournamentAchievementsUseCase(
        social_uow=social_uow,
        competition_uow=world.comp,
        golf_course_uow=world.golf,
        user_uow=world.users,
        differentials=StatsPlayerDifferentialsAdapter(stats),
        history=PlayerCourseHistoryAdapter(qm_uow or InMemoryQuickMatchUnitOfWork(), world.comp),
    )


async def _cerrar(world, social_uow, competition, quien) -> None:
    """Cierra el torneo como lo hace la API: el caso de uso con su publicador."""
    publish = _publisher(world, social_uow)
    await CompleteCompetitionUseCase(
        world.comp, achievements=TournamentAchievementsPublisher(publish)
    ).execute(CompleteCompetitionRequestDTO(competition_id=competition.id.value), quien.id)


async def _reabrir(world, social_uow, competition) -> None:
    competition.revert_to_in_progress()
    await world.save_competition(competition)
    await PublishCompetitionNoticesUseCase(social_uow, world.users).reopened(
        str(competition.id.value)
    )


async def _feed(social_uow, user):
    async with social_uow:
        return await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=100
        )


async def _de_tipo(social_uow, user, tipo):
    return [e for e in await _feed(social_uow, user) if e.type == tipo]


# ==================== 1. Campo nuevo ====================


class TestNewCourseOncePerTournament:
    async def test_two_stroke_play_rounds_on_a_new_course_announce_it_once(self, world, social_uow):
        ana = await world.user()
        competition = await world.competition(ana, enrolled=[ana])
        course = await world.course(ana)
        primera = await world.group(
            competition, await world.round(competition, course), {ana: tarjeta()}
        )
        segunda_ronda = await world.round(competition, course, DIA + timedelta(days=1))
        await world.group(competition, segunda_ronda, {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        nuevos = await _de_tipo(social_uow, ana, T.NEW_COURSE)
        assert [e.source_match_id for e in nuevos] == [str(primera.id.value)]

    async def test_two_ryder_matches_on_a_new_course_announce_it_once(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        competition = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        course = await world.course(ana)
        primero = await world.match(await world.round(competition, course), ana, rival, tarjeta())
        tarde = await world.round(competition, course, DIA + timedelta(days=1))
        await world.match(tarde, ana, rival, tarjeta())

        await _publisher(world, social_uow).execute(str(competition.id.value))

        nuevos = await _de_tipo(social_uow, ana, T.NEW_COURSE)
        assert [e.source_match_id for e in nuevos] == [str(primero.id.value)]

    async def test_two_courses_in_one_tournament_are_two_new_courses(self, world, social_uow):
        ana = await world.user()
        competition = await world.competition(ana, enrolled=[ana])
        uno = await world.course(ana)
        otro = await world.course(ana)
        await world.group(competition, await world.round(competition, uno), {ana: tarjeta()})
        segunda = await world.round(competition, otro, DIA + timedelta(days=1))
        await world.group(competition, segunda, {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 2

    async def test_a_course_played_in_a_closed_tournament_before_is_not_new(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana)
        anterior = await world.competition(ana, enrolled=[ana])
        await world.group(anterior, await world.round(anterior, course), {ana: tarjeta()})
        competition = await world.competition(ana, enrolled=[ana])
        ronda = await world.round(competition, course, DIA + timedelta(days=30))
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert await _de_tipo(social_uow, ana, T.NEW_COURSE) == []

    async def test_a_tournament_still_open_does_not_count_as_played(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        course = await world.course(ana)
        abierto = await world.competition(ana, enrolled=[ana], completed=False)
        await world.group(abierto, await world.round(abierto, course), {ana: tarjeta()})
        ryder_abierta = await world.competition(
            ana, tipo=RYDER, enrolled=[ana, rival], completed=False
        )
        await world.match(await world.round(ryder_abierta, course), ana, rival, tarjeta())
        competition = await world.competition(ana, enrolled=[ana])
        ronda = await world.round(competition, course, DIA + timedelta(days=30))
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1


# ==================== 5. Primer torneo: solo cuentan los cerrados ====================


class TestFirstTournamentCountsClosedOnes:
    async def test_a_stroke_play_tournament_still_open_is_not_a_previous_one(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana)
        abierto = await world.competition(ana, enrolled=[ana], completed=False)
        await world.group(abierto, await world.round(abierto, course), {ana: tarjeta()})
        competition = await world.competition(ana, enrolled=[ana])
        await world.group(competition, await world.round(competition, course), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)) == 1

    async def test_a_ryder_still_open_is_not_a_previous_one(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        course = await world.course(ana)
        abierta = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival], completed=False)
        await world.match(await world.round(abierta, course), ana, rival, tarjeta())
        competition = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        await world.match(await world.round(competition, course), ana, rival, tarjeta())

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)) == 1

    async def test_a_closed_ryder_is_a_previous_one(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        course = await world.course(ana)
        cerrada = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        await world.match(await world.round(cerrada, course), ana, rival, tarjeta())
        despues = DIA + timedelta(days=30)
        competition = await world.competition(ana, enrolled=[ana], start=despues)
        await world.group(
            competition, await world.round(competition, course, despues), {ana: tarjeta()}
        )

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT) == []


# ==================== 2. Mejor marca: contra la de antes del torneo ====================


class TestPersonalBestAgainstBeforeTheTournament:
    async def test_a_better_ryder_publishes_the_record(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        course = await world.course(ana)
        anterior = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        await world.match(await world.round(anterior, course), ana, rival, tarjeta(par=5))
        competition = await world.competition(
            ana, tipo=RYDER, enrolled=[ana, rival], completed=False
        )
        ronda = await world.round(competition, course, DIA + timedelta(days=30))
        partido = await world.match(ronda, ana, rival, tarjeta())

        await _cerrar(world, social_uow, competition, ana)

        (record,) = await _de_tipo(social_uow, ana, T.PERSONAL_BEST)
        assert record.source_match_id == str(partido.id.value)

    async def test_a_worse_ryder_publishes_no_record(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        course = await world.course(ana)
        anterior = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        await world.match(await world.round(anterior, course), ana, rival, tarjeta())
        competition = await world.competition(
            ana, tipo=RYDER, enrolled=[ana, rival], completed=False
        )
        ronda = await world.round(competition, course, DIA + timedelta(days=30))
        await world.match(ronda, ana, rival, tarjeta(par=5))

        await _cerrar(world, social_uow, competition, ana)

        assert await _de_tipo(social_uow, ana, T.PERSONAL_BEST) == []

    async def test_closing_again_after_reopening_publishes_the_record_again(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana)
        anterior = await world.competition(ana, enrolled=[ana])
        await world.group(anterior, await world.round(anterior, course), {ana: tarjeta(par=5)})
        competition = await world.competition(ana, enrolled=[ana], completed=False)
        ronda = await world.round(competition, course, DIA + timedelta(days=30))
        await world.group(competition, ronda, {ana: tarjeta()})
        await _cerrar(world, social_uow, competition, ana)

        await _reabrir(world, social_uow, competition)
        await _cerrar(world, social_uow, competition, ana)

        assert len(await _de_tipo(social_uow, ana, T.PERSONAL_BEST)) == 1


# ==================== 3 y 4. La Ryder lleva su torneo y se retira al reabrir ====================


class TestRyderAchievementsCarryTheirTournament:
    async def test_every_ryder_achievement_carries_the_competition(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        competition = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        course = await world.course(ana)
        await world.match(await world.round(competition, course), ana, rival, tarjeta(h4=3))

        await _publisher(world, social_uow).execute(str(competition.id.value))

        eventos = await _feed(social_uow, ana)
        assert {e.type for e in eventos} >= {T.BIRDIE, T.FIRST_TOURNAMENT, T.NEW_COURSE}
        assert all(e.payload["competition_id"] == str(competition.id.value) for e in eventos)
        assert all(e.payload["kind"] == "MATCH" for e in eventos)

    async def test_reopening_a_ryder_withdraws_and_closing_republishes(self, world, social_uow):
        ana = await world.user()
        rival = await world.user()
        competition = await world.competition(
            ana, tipo=RYDER, enrolled=[ana, rival], completed=False
        )
        course = await world.course(ana)
        await world.match(await world.round(competition, course), ana, rival, tarjeta(h4=3))
        await _cerrar(world, social_uow, competition, ana)

        await _reabrir(world, social_uow, competition)
        assert await _feed(social_uow, ana) == []

        await _cerrar(world, social_uow, competition, ana)
        assert len(await _de_tipo(social_uow, ana, T.BIRDIE)) == 1


# ==================== 6. El candado del torneo ====================


class TestTournamentLock:
    async def _espiar(self, social_uow, monkeypatch) -> list:
        llamadas: list = []
        repo = social_uow.activity_events
        for metodo in ("lock_scope", "add_many", "delete_for_competition", "delete_from_source"):
            original = getattr(repo, metodo)

            def _envolver(nombre, funcion):
                async def _llamada(*args, **kwargs):
                    llamadas.append((nombre, args[0] if nombre == "lock_scope" else None))
                    return await funcion(*args, **kwargs)

                return _llamada

            monkeypatch.setattr(repo, metodo, _envolver(metodo, original))
        return llamadas

    async def test_reopening_takes_the_tournament_lock_first(self, world, social_uow, monkeypatch):
        llamadas = await self._espiar(social_uow, monkeypatch)

        await PublishCompetitionNoticesUseCase(social_uow, world.users).reopened("torneo-1")

        assert llamadas[0] == ("lock_scope", "torneo-1")
        assert len(llamadas) > 1

    async def test_publishing_takes_the_tournament_lock_before_writing(
        self, world, social_uow, monkeypatch
    ):
        ana = await world.user()
        competition = await world.competition(ana, enrolled=[ana])
        course = await world.course(ana)
        await world.group(competition, await world.round(competition, course), {ana: tarjeta()})
        llamadas = await self._espiar(social_uow, monkeypatch)

        await _publisher(world, social_uow).execute(str(competition.id.value))

        assert llamadas[:2] == [("lock_scope", str(competition.id.value)), ("add_many", None)]


# ==================== Corte por fecha: ANTES del torneo (revision final) ====================


class TestOnlyWhatWasPlayedBefore:
    """
    «Campo nuevo» y «primer torneo» miran solo lo jugado ANTES: un torneo que
    se reabre y se vuelve a cerrar no pierde sus logros porque despues se
    jugara otra vez en el campo o se cerrara otro torneo.
    """

    async def test_a_later_closed_tournament_on_the_course_does_not_take_it_away(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana)
        primero = await world.competition(ana, enrolled=[ana])
        await world.group(primero, await world.round(primero, course), {ana: tarjeta()})
        despues = DIA + timedelta(days=30)
        luego = await world.competition(ana, enrolled=[ana], start=despues)
        await world.group(luego, await world.round(luego, course, despues), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(primero.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1
        assert len(await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)) == 1

    async def test_the_later_tournament_is_neither_new_course_nor_first(self, world, social_uow):
        ana = await world.user()
        course = await world.course(ana)
        primero = await world.competition(ana, enrolled=[ana])
        await world.group(primero, await world.round(primero, course), {ana: tarjeta()})
        despues = DIA + timedelta(days=30)
        luego = await world.competition(ana, enrolled=[ana], start=despues)
        await world.group(luego, await world.round(luego, course, despues), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(luego.id.value))

        assert await _de_tipo(social_uow, ana, T.NEW_COURSE) == []
        assert await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT) == []

    async def test_a_quick_match_played_after_the_round_does_not_take_it_away(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        await _partida_rapida(qm_uow, ana, course)  # se crea hoy, despues de DIA
        competition = await world.competition(ana, enrolled=[ana])
        await world.group(competition, await world.round(competition, course), {ana: tarjeta()})

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1

    async def test_a_quick_match_played_before_the_round_counts(self, world, social_uow):
        ana = await world.user()
        course = await world.course(ana)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        await _partida_rapida(qm_uow, ana, course)
        futuro = date.today() + timedelta(days=60)
        competition = await world.competition(ana, enrolled=[ana], start=futuro)
        ronda = await world.round(competition, course, futuro)
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert await _de_tipo(social_uow, ana, T.NEW_COURSE) == []


async def _partida_rapida(qm_uow, user, course, creada: datetime | None = None) -> None:
    """Una partida rapida terminada en ese campo, creada hoy o en `creada` (UTC sin zona)."""
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=user.id,
        golf_course_id=course.id,
        scoring_format=ScoringFormat.STABLEFORD,
    )
    match.start([match.creator_participant_id])
    match.complete()
    if creada is not None:
        match = QuickMatch.reconstruct(
            id=match.id,
            creator_id=match.creator_id,
            golf_course_id=match.golf_course_id,
            match_format=match.match_format,
            status=match.status,
            participants=list(match.participants),
            scoring_format=match.scoring_format,
            allowance_percentage=match.allowance_percentage,
            play_mode=match.play_mode,
            scorer_ids=list(match.scorer_ids),
            created_at=creada,
            updated_at=creada,
        )
    async with qm_uow:
        await qm_uow.quick_matches.add(match)


# ==================== El mismo dia, por hora real (prueba de punta a punta, 22 oct) ====================

MADRID = "Europe/Madrid"  # en junio, UTC+2: la sesion de manana abre a las 4:00 UTC
MANANA = SessionType.MORNING  # 6:00 locales
TARDE = SessionType.AFTERNOON  # 12:00 locales = 10:00 UTC en junio en Madrid


class TestNewCourseOnTheSameDay:
    """
    «Campo nuevo»: lo jugado ANTES de la primera vuelta del torneo en el campo
    cuenta como ya jugado aunque sea el mismo dia. La vuelta del torneo se fecha
    con la hora de apertura de su sesion en la zona del campo; la partida
    rapida, con su instante de creacion. Sin zona, por fecha: el mismo dia no
    cuenta.
    """

    async def test_a_quick_match_that_morning_takes_away_the_afternoon_round(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana, timezone=MADRID)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        await _partida_rapida(qm_uow, ana, course, datetime.combine(DIA, datetime.min.time()))
        competition = await world.competition(ana, enrolled=[ana])
        ronda = await world.round(competition, course, DIA, TARDE)
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert await _de_tipo(social_uow, ana, T.NEW_COURSE) == []

    async def test_a_quick_match_after_the_morning_round_does_not_take_it_away(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana, timezone=MADRID)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        await _partida_rapida(qm_uow, ana, course, datetime(DIA.year, DIA.month, DIA.day, 9, 0))
        competition = await world.competition(ana, enrolled=[ana])
        ronda = await world.round(competition, course, DIA, MANANA)
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1

    async def test_the_instant_is_the_session_in_the_course_zone_not_in_utc(
        self, world, social_uow
    ):
        """A las 11:00 UTC ya han pasado las 12:00 de Madrid (10:00 UTC): es despues."""
        ana = await world.user()
        course = await world.course(ana, timezone=MADRID)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        await _partida_rapida(qm_uow, ana, course, datetime(DIA.year, DIA.month, DIA.day, 11, 0))
        competition = await world.competition(ana, enrolled=[ana])
        ronda = await world.round(competition, course, DIA, TARDE)
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1

    async def test_without_the_course_zone_the_same_day_does_not_count(self, world, social_uow):
        ana = await world.user()
        course = await world.course(ana)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        await _partida_rapida(qm_uow, ana, course, datetime.combine(DIA, datetime.min.time()))
        competition = await world.competition(ana, enrolled=[ana])
        ronda = await world.round(competition, course, DIA, TARDE)
        await world.group(competition, ronda, {ana: tarjeta()})

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1

    async def test_the_day_before_still_counts_without_the_zone(self, world, social_uow):
        ana = await world.user()
        course = await world.course(ana)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        ayer = DIA - timedelta(days=1)
        await _partida_rapida(qm_uow, ana, course, datetime(ayer.year, ayer.month, ayer.day, 23))
        competition = await world.competition(ana, enrolled=[ana])
        await world.group(
            competition, await world.round(competition, course, DIA, TARDE), {ana: tarjeta()}
        )

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        assert await _de_tipo(social_uow, ana, T.NEW_COURSE) == []

    async def test_a_closed_tournament_that_morning_on_the_course_takes_it_away(
        self, world, social_uow
    ):
        """En el mismo campo la zona es la misma: basta el orden de las sesiones."""
        ana = await world.user()
        course = await world.course(ana)
        manana = await world.competition(ana, enrolled=[ana])
        await world.group(manana, await world.round(manana, course, DIA, MANANA), {ana: tarjeta()})
        tarde = await world.competition(ana, enrolled=[ana])
        await world.group(tarde, await world.round(tarde, course, DIA, TARDE), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(tarde.id.value))

        assert await _de_tipo(social_uow, ana, T.NEW_COURSE) == []

    async def test_a_closed_tournament_that_afternoon_does_not_take_it_away(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana, timezone=MADRID)
        manana = await world.competition(ana, enrolled=[ana])
        await world.group(manana, await world.round(manana, course, DIA, MANANA), {ana: tarjeta()})
        tarde = await world.competition(ana, enrolled=[ana])
        await world.group(tarde, await world.round(tarde, course, DIA, TARDE), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(manana.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1

    async def test_the_same_session_of_another_tournament_does_not_take_it_away(
        self, world, social_uow
    ):
        ana = await world.user()
        course = await world.course(ana)
        uno = await world.competition(ana, enrolled=[ana])
        await world.group(uno, await world.round(uno, course, DIA, MANANA), {ana: tarjeta()})
        otro = await world.competition(ana, enrolled=[ana])
        await world.group(otro, await world.round(otro, course, DIA, MANANA), {ana: tarjeta()})

        await _publisher(world, social_uow).execute(str(otro.id.value))

        assert len(await _de_tipo(social_uow, ana, T.NEW_COURSE)) == 1

    async def test_the_morning_round_of_the_tournament_is_the_first_one(
        self, world, social_uow, monkeypatch
    ):
        """Dos rondas el mismo dia: el campo se estrena en la de la manana."""
        # La de la tarde con el id menor: si el orden fuera por id, ganaria ella
        ids = iter([PartidaId(UUID(int=1)), PartidaId(UUID(int=2))])
        monkeypatch.setattr(PartidaId, "generate", classmethod(lambda cls: next(ids)))
        ana = await world.user()
        course = await world.course(ana, timezone=MADRID)
        qm_uow = InMemoryQuickMatchUnitOfWork()
        # Entre las dos: despues de las 4:00 UTC y antes de las 10:00 UTC
        await _partida_rapida(qm_uow, ana, course, datetime(DIA.year, DIA.month, DIA.day, 7, 0))
        competition = await world.competition(ana, enrolled=[ana])
        tarde = await world.group(
            competition, await world.round(competition, course, DIA, TARDE), {ana: tarjeta()}
        )
        manana = await world.group(
            competition, await world.round(competition, course, DIA, MANANA), {ana: tarjeta()}
        )
        assert tarde.id != manana.id

        await _publisher(world, social_uow, qm_uow).execute(str(competition.id.value))

        nuevos = await _de_tipo(social_uow, ana, T.NEW_COURSE)
        assert [e.source_match_id for e in nuevos] == [str(manana.id.value)]


class TestFirstTournamentOnTheSameDay:
    """
    «Primer torneo» con dos torneos que empiezan el mismo dia: solo lo da uno.
    Criterio (decision de este arreglo): el que empieza antes; si empiezan el
    mismo dia, aquel en el que el jugador jugo antes su primera vuelta (fecha y
    hora local de la sesion); y si tambien coinciden, el de id menor.
    """

    async def _dos_torneos(self, world, sesion_a, sesion_b):
        """
        Dos torneos que empiezan el mismo dia. `a` es SIEMPRE el de id mayor:
        asi, si la hora no decidiera, el desempate por id daria el otro.
        """
        ana = await world.user()
        course = await world.course(ana)
        uno = await world.competition(ana, enrolled=[ana])
        otro = await world.competition(ana, enrolled=[ana])
        b, a = sorted((uno, otro), key=lambda c: str(c.id.value))
        await world.group(a, await world.round(a, course, DIA, sesion_a), {ana: tarjeta()})
        await world.group(b, await world.round(b, course, DIA, sesion_b), {ana: tarjeta()})
        return ana, a, b

    async def test_only_the_one_played_first_that_day_is_the_first(self, world, social_uow):
        ana, manana, tarde = await self._dos_torneos(world, MANANA, TARDE)

        await _publisher(world, social_uow).execute(str(tarde.id.value))
        await _publisher(world, social_uow).execute(str(manana.id.value))

        primeros = await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)
        assert [e.payload["competition_id"] for e in primeros] == [str(manana.id.value)]

    async def test_in_the_same_session_the_lower_id_wins(self, world, social_uow):
        ana, a, b = await self._dos_torneos(world, MANANA, MANANA)

        await _publisher(world, social_uow).execute(str(a.id.value))
        await _publisher(world, social_uow).execute(str(b.id.value))

        primeros = await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)
        menor = min(str(a.id.value), str(b.id.value))
        assert [e.payload["competition_id"] for e in primeros] == [menor]

    async def test_reopening_and_closing_both_again_gives_the_same(self, world, social_uow):
        ana, manana, tarde = await self._dos_torneos(world, MANANA, TARDE)
        for torneo in (tarde, manana):
            await _publisher(world, social_uow).execute(str(torneo.id.value))

        for torneo in (manana, tarde):
            await _reabrir(world, social_uow, torneo)
            torneo.complete()
            await world.save_competition(torneo)
            await _publisher(world, social_uow).execute(str(torneo.id.value))

        primeros = await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)
        assert [e.payload["competition_id"] for e in primeros] == [str(manana.id.value)]
        nuevos = await _de_tipo(social_uow, ana, T.NEW_COURSE)
        assert [e.payload["competition_id"] for e in nuevos] == [str(manana.id.value)]

    async def test_it_is_the_first_round_of_the_player_that_decides(self, world, social_uow):
        """Manana y noche en uno, tarde en el otro: gana el de la manana."""
        ana, a, b = await self._dos_torneos(world, SessionType.MORNING, TARDE)
        course = await world.course(ana)
        noche = await world.round(a, course, DIA, SessionType.EVENING)
        await world.group(a, noche, {ana: tarjeta()}, numero=2)

        await _publisher(world, social_uow).execute(str(a.id.value))
        await _publisher(world, social_uow).execute(str(b.id.value))

        primeros = await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)
        assert [e.payload["competition_id"] for e in primeros] == [str(a.id.value)]

    async def test_a_ryder_the_same_day_is_tied_by_its_match(self, world, social_uow):
        """El otro torneo es una Ryder: su primera vuelta sale de sus partidos."""
        ana = await world.user()
        rival = await world.user()
        course = await world.course(ana)
        uno = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        otro = await world.competition(ana, enrolled=[ana])
        # El de id mayor juega por la manana: sin la hora, el id daria el otro
        if str(uno.id.value) > str(otro.id.value):
            await world.match(await world.round(uno, course, DIA, MANANA), ana, rival, tarjeta())
            await world.group(otro, await world.round(otro, course, DIA, TARDE), {ana: tarjeta()})
            primero = uno
        else:
            await world.match(await world.round(uno, course, DIA, TARDE), ana, rival, tarjeta())
            await world.group(otro, await world.round(otro, course, DIA, MANANA), {ana: tarjeta()})
            primero = otro

        await _publisher(world, social_uow).execute(str(uno.id.value))
        await _publisher(world, social_uow).execute(str(otro.id.value))

        primeros = await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT)
        assert [e.payload["competition_id"] for e in primeros] == [str(primero.id.value)]

    async def test_a_tournament_that_started_earlier_still_wins(self, world, social_uow):
        """El dia de inicio sigue mandando: la hora solo desempata el mismo dia."""
        ana = await world.user()
        course = await world.course(ana)
        antes = await world.competition(ana, enrolled=[ana], start=DIA - timedelta(days=1))
        # Su vuelta, por la tarde del dia siguiente: el torneo empezo antes
        await world.group(antes, await world.round(antes, course, DIA, TARDE), {ana: tarjeta()})
        despues = await world.competition(ana, enrolled=[ana])
        await world.group(
            despues, await world.round(despues, course, DIA, MANANA), {ana: tarjeta()}
        )

        await _publisher(world, social_uow).execute(str(despues.id.value))

        assert await _de_tipo(social_uow, ana, T.FIRST_TOURNAMENT) == []


class TestPlayerIdsOfTheMatch:
    """Los logros de la Ryder llevan `player_ids`: los del partido, ordenados (22 oct)."""

    async def test_every_ryder_achievement_carries_the_players_of_its_match(
        self, world, social_uow
    ):
        ana = await world.user()
        rival = await world.user()
        competition = await world.competition(ana, tipo=RYDER, enrolled=[ana, rival])
        course = await world.course(ana)
        await world.match(await world.round(competition, course), ana, rival, tarjeta(h4=3))

        await _publisher(world, social_uow).execute(str(competition.id.value))

        esperado = sorted(str(u.id.value) for u in (ana, rival))
        eventos = await _feed(social_uow, ana)
        assert eventos
        assert all(e.payload["player_ids"] == esperado for e in eventos)
