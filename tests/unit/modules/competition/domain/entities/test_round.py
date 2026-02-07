"""Tests para Round entity."""

from datetime import date, datetime

import pytest

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class TestRoundCreate:
    """Tests para creación de Round"""

    def test_create_round_with_valid_data(self):
        """Crea una sesión con datos válidos."""
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()

        round = Round.create(
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
        )

        assert round.id is not None
        assert round.competition_id == competition_id
        assert round.golf_course_id == golf_course_id
        assert round.round_date == date(2026, 3, 15)
        assert round.session_type == SessionType.MORNING
        assert round.match_format == MatchFormat.FOURBALL
        assert round.status == RoundStatus.PENDING_TEAMS

    def test_create_round_sets_timestamps(self):
        """create() establece created_at y updated_at."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.SINGLES,
        )

        assert round.created_at is not None
        assert round.updated_at is not None


class TestRoundReconstruct:
    """Tests para reconstrucción de Round"""

    def test_reconstruct_from_db(self):
        """Reconstruye una sesión desde BD."""
        round_id = RoundId.generate()
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()
        created = datetime(2026, 1, 1, 10, 0)
        updated = datetime(2026, 1, 2, 15, 0)

        round = Round.reconstruct(
            id=round_id,
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 3, 15),
            session_type=SessionType.EVENING,
            match_format=MatchFormat.FOURSOMES,
            status=RoundStatus.SCHEDULED,
            handicap_mode=None,  # FOURSOMES no usa handicap_mode
            allowance_percentage=50,
            created_at=created,
            updated_at=updated,
        )

        assert round.id == round_id
        assert round.status == RoundStatus.SCHEDULED
        assert round.handicap_mode is None
        assert round.allowance_percentage == 50
        assert round.created_at == created
        assert round.updated_at == updated


class TestRoundStatusTransitions:
    """Tests para transiciones de estado"""

    def test_mark_teams_assigned_from_pending_teams(self):
        """PENDING_TEAMS → PENDING_MATCHES."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        round.mark_teams_assigned()

        assert round.status == RoundStatus.PENDING_MATCHES

    def test_mark_teams_assigned_from_wrong_status_raises(self):
        """mark_teams_assigned desde estado incorrecto lanza error."""
        round = Round.reconstruct(
            id=RoundId.generate(),
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            status=RoundStatus.SCHEDULED,
            handicap_mode=HandicapMode.MATCH_PLAY,
            allowance_percentage=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        with pytest.raises(ValueError, match="Expected PENDING_TEAMS"):
            round.mark_teams_assigned()

    def test_mark_matches_generated_from_pending_matches(self):
        """PENDING_MATCHES → SCHEDULED."""
        round = Round.reconstruct(
            id=RoundId.generate(),
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            status=RoundStatus.PENDING_MATCHES,
            handicap_mode=HandicapMode.MATCH_PLAY,
            allowance_percentage=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        round.mark_matches_generated()

        assert round.status == RoundStatus.SCHEDULED

    def test_start_from_scheduled(self):
        """SCHEDULED → IN_PROGRESS."""
        round = Round.reconstruct(
            id=RoundId.generate(),
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            status=RoundStatus.SCHEDULED,
            handicap_mode=HandicapMode.MATCH_PLAY,
            allowance_percentage=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        round.start()

        assert round.status == RoundStatus.IN_PROGRESS

    def test_complete_from_in_progress(self):
        """IN_PROGRESS → COMPLETED."""
        round = Round.reconstruct(
            id=RoundId.generate(),
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            status=RoundStatus.IN_PROGRESS,
            handicap_mode=HandicapMode.MATCH_PLAY,
            allowance_percentage=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        round.complete()

        assert round.status == RoundStatus.COMPLETED


class TestRoundUpdateDetails:
    """Tests para actualización de detalles"""

    def test_update_details_in_pending_status(self):
        """Se pueden actualizar detalles en estado PENDING."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        new_course = GolfCourseId.generate()

        round.update_details(
            round_date=date(2026, 3, 16),
            session_type=SessionType.AFTERNOON,
            golf_course_id=new_course,
        )

        assert round.round_date == date(2026, 3, 16)
        assert round.session_type == SessionType.AFTERNOON
        assert round.golf_course_id == new_course

    def test_update_details_in_scheduled_raises(self):
        """No se puede modificar en estado SCHEDULED."""
        round = Round.reconstruct(
            id=RoundId.generate(),
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            status=RoundStatus.SCHEDULED,
            handicap_mode=HandicapMode.MATCH_PLAY,
            allowance_percentage=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        with pytest.raises(ValueError, match="Cannot modify"):
            round.update_details(round_date=date(2026, 3, 16))


class TestRoundQueryMethods:
    """Tests para métodos de consulta"""

    def test_players_per_match_singles(self):
        """SINGLES tiene 2 jugadores por partido (1 vs 1)."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        assert round.players_per_match() == 2
        assert round.players_per_team_in_match() == 1

    def test_players_per_match_fourball(self):
        """FOURBALL tiene 4 jugadores por partido (2 vs 2)."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
        )

        assert round.players_per_match() == 4
        assert round.players_per_team_in_match() == 2


class TestRoundEquality:
    """Tests para igualdad y hash"""

    def test_rounds_with_same_id_are_equal(self):
        """Rounds con mismo ID son iguales."""
        round_id = RoundId.generate()
        now = datetime.now()

        round1 = Round.reconstruct(
            id=round_id,
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            status=RoundStatus.PENDING_TEAMS,
            handicap_mode=HandicapMode.MATCH_PLAY,
            allowance_percentage=None,
            created_at=now,
            updated_at=now,
        )
        round2 = Round.reconstruct(
            id=round_id,
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 16),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.FOURBALL,
            status=RoundStatus.COMPLETED,
            handicap_mode=None,
            allowance_percentage=90,
            created_at=now,
            updated_at=now,
        )

        assert round1 == round2

    def test_rounds_with_different_id_are_not_equal(self):
        """Rounds con diferente ID no son iguales."""
        round1 = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round2 = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        assert round1 != round2

    def test_round_can_be_used_in_set(self):
        """Round puede usarse en set."""
        round1 = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        round_set = {round1}
        assert round1 in round_set


class TestRoundHandicapConfiguration:
    """Tests para configuración de handicap"""

    def test_singles_defaults_to_match_play_mode(self):
        """SINGLES sin handicap_mode usa MATCH_PLAY por defecto."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        assert round.handicap_mode == HandicapMode.MATCH_PLAY
        assert round.allowance_percentage is None

    def test_fourball_ignores_handicap_mode(self):
        """FOURBALL ignora handicap_mode (es siempre None)."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
            handicap_mode=HandicapMode.MATCH_PLAY,  # Debería ignorarse
        )

        assert round.handicap_mode is None

    def test_foursomes_ignores_handicap_mode(self):
        """FOURSOMES ignora handicap_mode (es siempre None)."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURSOMES,
            handicap_mode=HandicapMode.MATCH_PLAY,  # Debería ignorarse
        )

        assert round.handicap_mode is None

    def test_custom_allowance_percentage_valid(self):
        """Puede configurar porcentaje de allowance válido."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            allowance_percentage=85,
        )

        assert round.allowance_percentage == 85

    def test_invalid_allowance_percentage_raises(self):
        """Error si allowance_percentage no es múltiplo de 5."""
        with pytest.raises(ValueError, match="allowance_percentage must be one of"):
            Round.create(
                competition_id=CompetitionId.generate(),
                golf_course_id=GolfCourseId.generate(),
                round_date=date(2026, 3, 15),
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
                allowance_percentage=73,  # No válido
            )

    def test_allowance_below_50_raises(self):
        """Error si allowance_percentage es menor que 50."""
        with pytest.raises(ValueError, match="allowance_percentage must be one of"):
            Round.create(
                competition_id=CompetitionId.generate(),
                golf_course_id=GolfCourseId.generate(),
                round_date=date(2026, 3, 15),
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
                allowance_percentage=45,
            )

    def test_allowance_above_100_raises(self):
        """Error si allowance_percentage es mayor que 100."""
        with pytest.raises(ValueError, match="allowance_percentage must be one of"):
            Round.create(
                competition_id=CompetitionId.generate(),
                golf_course_id=GolfCourseId.generate(),
                round_date=date(2026, 3, 15),
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
                allowance_percentage=105,
            )


class TestRoundEffectiveAllowance:
    """Tests para get_effective_allowance()"""

    def test_singles_match_play_default_100(self):
        """SINGLES MATCH_PLAY usa 100% por defecto."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            handicap_mode=HandicapMode.MATCH_PLAY,
        )

        assert round.get_effective_allowance() == 100

    def test_fourball_default_90(self):
        """FOURBALL usa 90% por defecto."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
        )

        assert round.get_effective_allowance() == 90

    def test_foursomes_default_50(self):
        """FOURSOMES usa 50% por defecto (de la diferencia)."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURSOMES,
        )

        assert round.get_effective_allowance() == 50

    def test_custom_allowance_overrides_default(self):
        """Custom allowance reemplaza el default."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
            allowance_percentage=85,
        )

        assert round.get_effective_allowance() == 85


class TestRoundUpdateHandicapSettings:
    """Tests para actualizar configuración de handicap"""

    def test_update_handicap_mode_for_singles(self):
        """Puede actualizar handicap_mode en SINGLES."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            handicap_mode=HandicapMode.MATCH_PLAY,
        )

        round.update_details(handicap_mode=HandicapMode.MATCH_PLAY)

        assert round.handicap_mode == HandicapMode.MATCH_PLAY

    def test_update_allowance_percentage(self):
        """Puede actualizar allowance_percentage."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        round.update_details(allowance_percentage=90)

        assert round.allowance_percentage == 90

    def test_clear_allowance_returns_to_default(self):
        """clear_allowance vuelve al default WHS."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            allowance_percentage=85,
        )

        round.update_details(clear_allowance=True)

        assert round.allowance_percentage is None
        assert round.get_effective_allowance() == 100  # Default MATCH_PLAY

    def test_change_format_to_fourball_clears_handicap_mode(self):
        """Cambiar a FOURBALL limpia handicap_mode."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
            handicap_mode=HandicapMode.MATCH_PLAY,
        )

        round.update_details(match_format=MatchFormat.FOURBALL)

        assert round.match_format == MatchFormat.FOURBALL
        assert round.handicap_mode is None

    def test_change_format_to_singles_sets_default_mode(self):
        """Cambiar a SINGLES establece MATCH_PLAY por defecto."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.FOURBALL,
        )

        round.update_details(match_format=MatchFormat.SINGLES)

        assert round.match_format == MatchFormat.SINGLES
        assert round.handicap_mode == HandicapMode.MATCH_PLAY

    def test_update_invalid_allowance_raises(self):
        """Error al actualizar con allowance inválido."""
        round = Round.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 3, 15),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

        with pytest.raises(ValueError, match="allowance_percentage must be one of"):
            round.update_details(allowance_percentage=42)
