"""
Tests de GetLeaderboardUseCase, centrados en cómo se resuelve el nombre de
cada jugador.

La clasificación pinta `display_name` (BE #239) salvo que la inscripción de
esa persona en ESTA competición haya elegido su nombre legal (BE #254). No
existía ningún test de este caso de uso antes de esta issue.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def user_repo():
    """Un repositorio donde `display_name` NO coincide con nombre+apellido."""

    def _make(uid):
        user = MagicMock()
        user.id = uid
        user.first_name = "Nombre"
        user.last_name = "Legal"
        user.display_name = "Chuchi"
        user.get_full_name = MagicMock(return_value="Nombre Legal")
        user.display_name_or_legal = MagicMock(
            side_effect=lambda real: "Nombre Legal" if real else "Chuchi"
        )
        return user

    repo = AsyncMock()
    repo.find_by_ids = AsyncMock(side_effect=lambda uids: [_make(u) for u in uids])
    return repo


async def _setup_scheduled_match(uow: InMemoryUnitOfWork):
    """
    Una competición con una ronda y un partido SCHEDULED entre dos jugadores.

    SCHEDULED no está terminado ni admite anotación (`can_record_scores()` es
    False), así que el caso de uso no entra en ninguna de las dos ramas de
    cálculo de resultado: lo único que se ejercita es la resolución del
    nombre de cada jugador, que es lo único que prueba este fichero.
    """
    player_a = MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )
    player_b = MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=18,
        tee_color=TeeColor.RED,
        tee_gender=Gender.FEMALE,
        strokes_received=[],
    )

    round_id = RoundId.generate()
    competition_id = CompetitionId.generate()

    mock_round = MagicMock()
    mock_round.id = round_id
    mock_round.competition_id = competition_id
    mock_round.match_format = MagicMock(value="SINGLES")
    mock_round.round_date = None
    mock_round.session_type = None

    match = Match.create(
        round_id=round_id, match_number=1, team_a_players=[player_a], team_b_players=[player_b]
    )
    await uow.matches.add(match)
    uow._rounds._rounds[round_id] = mock_round

    mock_comp = MagicMock()
    mock_comp.id = competition_id
    mock_comp.name = "Test Cup"
    mock_comp.tournament_type = TournamentType.RYDER_CUP
    mock_comp.ryder_cup.team_1_name = "Team A"
    mock_comp.ryder_cup.team_2_name = "Team B"
    mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
    uow._competitions._competitions[competition_id] = mock_comp

    return competition_id, player_a, player_b


class TestLeaderboardPaintsTheDisplayName:
    """La clasificación pinta `display_name` por defecto (BE #239)."""

    @pytest.mark.asyncio
    async def test_players_are_named_by_their_display_name(self, uow, user_repo):
        competition_id, player_a, _player_b = await _setup_scheduled_match(uow)
        uc = GetLeaderboardUseCase(uow, user_repo, ScoringService())

        view = await uc.execute(str(competition_id))

        names = {p.user_id for m in view.matches for p in (*m.team_a_players, *m.team_b_players)}
        user_names = {
            p.user_name for m in view.matches for p in (*m.team_a_players, *m.team_b_players)
        }
        assert str(player_a.user_id) in names
        assert user_names == {"Chuchi"}


class TestLeaderboardRespectsNamePreference:
    """
    Salvo que la inscripción de esa competición haya elegido el nombre legal
    (BE #254), en cuyo caso ese jugador se pinta por su nombre y el resto
    sigue por su alias.
    """

    @pytest.mark.asyncio
    async def test_el_jugador_que_eligio_su_nombre_legal_se_pinta_por_el(self, uow, user_repo):
        competition_id, player_a, player_b = await _setup_scheduled_match(uow)
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=competition_id,
            user_id=player_a.user_id,
        )
        enrollment.set_name_preference(True)
        await uow.enrollments.add(enrollment)

        uc = GetLeaderboardUseCase(uow, user_repo, ScoringService())
        view = await uc.execute(str(competition_id))

        user_names = {
            p.user_id: p.user_name
            for m in view.matches
            for p in (*m.team_a_players, *m.team_b_players)
        }
        assert user_names[str(player_a.user_id)] == "Nombre Legal"
        assert user_names[str(player_b.user_id)] == "Chuchi"

    @pytest.mark.asyncio
    async def test_no_se_pierde_entre_muchas_otras_inscripciones_de_la_competicion(
        self, uow, user_repo
    ):
        """
        Una competición cuyas inscripciones han acumulado con el tiempo
        muchas más filas que jugadores a la vez —peticiones rechazadas,
        retiros, altas de nuevo— tiene que seguir viendo la preferencia de
        cualquiera de ellos: la búsqueda va acotada a los `user_ids` que
        aparecen en la clasificación, no a traer la competición entera.
        """
        competition_id, player_a, _player_b = await _setup_scheduled_match(uow)

        # Inscripciones de relleno de otros usuarios, ajenas al partido.
        for _ in range(105):
            filler = Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=UserId.generate(),
            )
            await uow.enrollments.add(filler)

        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=competition_id,
            user_id=player_a.user_id,
        )
        enrollment.set_name_preference(True)
        await uow.enrollments.add(enrollment)

        uc = GetLeaderboardUseCase(uow, user_repo, ScoringService())
        view = await uc.execute(str(competition_id))

        user_names = {
            p.user_id: p.user_name
            for m in view.matches
            for p in (*m.team_a_players, *m.team_b_players)
        }
        assert user_names[str(player_a.user_id)] == "Nombre Legal"


class TestLeaderboardConcededMatch:
    """BE #384, el gemelo de la vista de anotacion: la clasificacion sacaba el
    ganador de un partido concedido de los hoyos, y los puntos de la concesion.
    Si A iba ganando y concedia, decia «gana A» con el punto para B."""

    @pytest.mark.asyncio
    async def test_manda_la_concesion_y_no_los_hoyos(self, uow, user_repo):
        competition_id, _a, _b = await _setup_scheduled_match(uow)
        match = next(iter(uow._matches._matches.values()))
        match.start()
        match.mark_decided({"winner": "A", "score": "4&2"})
        match.concede("A")
        uc = GetLeaderboardUseCase(uow, user_repo, ScoringService())

        view = await uc.execute(str(competition_id))

        resultado = view.matches[0].result
        assert (resultado.winner, resultado.score) == ("B", "CONCEDED")
        assert (view.team_a_points, view.team_b_points) == (0.0, 1.0)


def _jugador():
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )


async def _sesion(uow, competition_id, dia, sesion, numero=1):
    """Una ronda con su fecha y su sesión, y un partido programado en ella."""
    ronda = MagicMock()
    ronda.id = RoundId.generate()
    ronda.competition_id = competition_id
    ronda.match_format = MagicMock(value="SINGLES")
    ronda.round_date = dia
    ronda.session_type = sesion
    uow._rounds._rounds[ronda.id] = ronda
    partido = Match.create(
        round_id=ronda.id,
        match_number=numero,
        team_a_players=[_jugador()],
        team_b_players=[_jugador()],
    )
    await uow.matches.add(partido)
    return partido


def _competicion(uow):
    competition_id = CompetitionId.generate()
    comp = MagicMock()
    comp.id = competition_id
    comp.name = "Test Cup"
    comp.ryder_cup.team_1_name = "Europa"
    comp.ryder_cup.team_2_name = "Estados Unidos"
    comp.require_ryder_cup.return_value = comp.ryder_cup
    uow._competitions._competitions[competition_id] = comp
    return competition_id


class TestLeaderboardSaysTheSessionOfEachMatch:
    """Cada partido dice de qué sesión es (BE #388): con varias sesiones
    salían dos «#2 - SINGLES» seguidos sin forma de distinguirlos."""

    @pytest.mark.asyncio
    async def test_a_match_carries_the_date_and_session_of_its_round(self, uow, user_repo):
        competition_id = _competicion(uow)
        await _sesion(uow, competition_id, date(2026, 9, 25), SessionType.MORNING)

        view = await GetLeaderboardUseCase(uow, user_repo, ScoringService()).execute(
            str(competition_id)
        )

        assert view.matches[0].round_date == date(2026, 9, 25)
        assert view.matches[0].session_type == "MORNING"

    @pytest.mark.asyncio
    async def test_matches_with_the_same_number_keep_their_own_session(self, uow, user_repo):
        competition_id = _competicion(uow)
        viernes = await _sesion(uow, competition_id, date(2026, 9, 25), SessionType.MORNING, 2)
        sabado = await _sesion(uow, competition_id, date(2026, 9, 26), SessionType.AFTERNOON, 2)

        view = await GetLeaderboardUseCase(uow, user_repo, ScoringService()).execute(
            str(competition_id)
        )

        por_id = {m.match_id: m for m in view.matches}
        assert (por_id[str(viernes.id)].round_date, por_id[str(viernes.id)].session_type) == (
            date(2026, 9, 25),
            "MORNING",
        )
        assert (por_id[str(sabado.id)].round_date, por_id[str(sabado.id)].session_type) == (
            date(2026, 9, 26),
            "AFTERNOON",
        )

    @pytest.mark.asyncio
    async def test_an_old_round_without_session_does_not_break_the_leaderboard(
        self, uow, user_repo
    ):
        competition_id = _competicion(uow)
        await _sesion(uow, competition_id, None, None)

        view = await GetLeaderboardUseCase(uow, user_repo, ScoringService()).execute(
            str(competition_id)
        )

        assert view.matches[0].round_date is None
        assert view.matches[0].session_type is None


class TestLaClasificacionDeUnStrokePlay:
    """
    Un Stableford o un Medal todavía no tiene clasificación (#251).

    Respondía «Un Stableford no tiene equipos», porque la clasificación pedía
    los equipos sin mirar el tipo. Decidido por Agustín el 4 oct 2026: el motivo
    dice que la clasificación llega con sus rondas, y se comprueba antes de
    leer rondas y partidos.
    """

    @staticmethod
    async def _stroke_play(uow, tipo):
        from src.modules.competition.domain.entities.competition import Competition
        from src.modules.competition.domain.value_objects.competition_name import (
            CompetitionName,
        )
        from src.modules.competition.domain.value_objects.date_range import DateRange
        from src.modules.competition.domain.value_objects.location import Location
        from src.shared.domain.value_objects.country_code import CountryCode
        from src.shared.domain.value_objects.play_mode import PlayMode

        competicion = Competition(
            id=CompetitionId.generate(),
            creator_id=UserId.generate(),
            name=CompetitionName("Torneo del club"),
            dates=DateRange(date(2030, 6, 1), date(2030, 6, 3)),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=tipo,
        )
        uow._competitions._competitions[competicion.id] = competicion
        return competicion

    @pytest.mark.asyncio
    @pytest.mark.parametrize("nombre", ["STABLEFORD", "MEDAL"])
    async def test_c1_dice_que_su_clasificacion_llega_con_sus_rondas(self, uow, user_repo, nombre):
        from src.modules.competition.domain.entities.competition import TournamentTypeError
        from src.modules.competition.domain.value_objects.tournament_type import (
            TournamentType,
        )

        tipo = TournamentType(nombre)
        competicion = await self._stroke_play(uow, tipo)
        use_case = GetLeaderboardUseCase(uow, user_repo, ScoringService())

        with pytest.raises(TournamentTypeError) as error:
            await use_case.execute(str(competicion.id))

        assert str(error.value) == (
            f"La clasificación de un {tipo.label} llega con sus rondas: "
            "todavía no se puede consultar"
        )

    @pytest.mark.asyncio
    async def test_c2_lo_dice_antes_de_leer_rondas(self, uow, user_repo):
        from src.modules.competition.domain.entities.competition import TournamentTypeError
        from src.modules.competition.domain.value_objects.tournament_type import (
            TournamentType,
        )

        competicion = await self._stroke_play(uow, TournamentType.MEDAL)
        uow._rounds.find_by_competition = AsyncMock(side_effect=AssertionError("leyó rondas"))
        use_case = GetLeaderboardUseCase(uow, user_repo, ScoringService())

        with pytest.raises(TournamentTypeError):
            await use_case.execute(str(competicion.id))
