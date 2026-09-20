"""La competicion guarda a que hora abren solas sus inscripciones (BE #319).

La hora se guarda tal como la escribe el organizador, sin huso: son las nueve
del campo donde se juega. Quien la interpreta es
[`EnrollmentOpeningService`][], que tiene sus propios tests; aqui se mira lo que
le toca a la entidad — que el dato se guarde, se pueda corregir, y que solo un
borrador se abra.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

MADRID = "Europe/Madrid"
AYER = (datetime.now(ZoneInfo(MADRID)) - timedelta(days=1)).replace(tzinfo=None)
MANANA = (datetime.now(ZoneInfo(MADRID)) + timedelta(days=1)).replace(tzinfo=None)


def build_competition(**overrides) -> Competition:
    argumentos = {
        "id": CompetitionId.generate(),
        "creator_id": UserId(str(CompetitionId.generate().value)),
        "name": CompetitionName("Ryder Cup Madrid 2026"),
        "dates": DateRange(date(2027, 6, 1), date(2027, 6, 3)),
        "location": Location(CountryCode("ES")),
        "team_1_name": "Europe",
        "team_2_name": "USA",
        "play_mode": PlayMode.HANDICAP,
    }
    argumentos.update(overrides)
    return Competition(**argumentos)


class TestTheOpeningDate:
    """El dato en si: opcional, y se puede corregir."""

    def test_there_is_no_date_by_default(self):
        """Entre amigos no se programa nada: se invita y ya."""
        assert build_competition().enrollment_opens_at is None

    def test_the_date_can_be_set_on_creation(self):
        assert build_competition(enrollment_opens_at=MANANA).enrollment_opens_at == MANANA

    def test_the_date_can_be_changed_later(self):
        competition = build_competition(enrollment_opens_at=MANANA)
        otra = MANANA + timedelta(days=2)

        competition.update_info(enrollment_opens_at=otra)

        assert competition.enrollment_opens_at == otra


class TestWhenItOpensByItself:
    """Solo un borrador se abre, y solo si ya paso su hora."""

    def test_a_past_hour_is_due(self):
        assert build_competition(enrollment_opens_at=AYER).due_to_open(MADRID) is True

    def test_a_future_hour_is_not(self):
        assert build_competition(enrollment_opens_at=MANANA).due_to_open(MADRID) is False

    def test_without_a_date_nothing_is_due(self):
        assert build_competition().due_to_open(MADRID) is False

    def test_without_a_course_it_waits(self):
        """Sin campo no hay zona, y sin zona no se abre a ciegas."""
        assert build_competition(enrollment_opens_at=AYER).due_to_open(None) is False

    @pytest.mark.parametrize(
        "status",
        [
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
            CompetitionStatus.COMPLETED,
            CompetitionStatus.CANCELLED,
        ],
    )
    def test_only_a_draft_is_due(self, status):
        """Una cancelada no resucita porque pase su hora, ni se reabre una cerrada."""
        competition = build_competition(status=status, enrollment_opens_at=AYER)

        assert competition.due_to_open(MADRID) is False

    def test_once_open_there_is_nothing_left_to_do(self):
        competition = build_competition(enrollment_opens_at=AYER)

        competition.activate()

        assert competition.status == CompetitionStatus.ACTIVE
        assert competition.due_to_open(MADRID) is False


class TestTheOpeningFitsTheTournament:
    """Abrir inscripciones despues de empezar a jugar no significa nada."""

    def test_opening_before_the_start_is_fine(self):
        competition = build_competition(enrollment_opens_at=datetime(2027, 5, 20, 9, 0))

        assert competition.enrollment_opens_at == datetime(2027, 5, 20, 9, 0)

    def test_opening_on_the_first_day_is_fine(self):
        """Se abre por la manana y se juega por la tarde: pasa en torneos de un dia."""
        competition = build_competition(enrollment_opens_at=datetime(2027, 6, 1, 8, 0))

        assert competition.enrollment_opens_at == datetime(2027, 6, 1, 8, 0)

    def test_opening_after_the_start_is_refused(self):
        """Apuntarse a un torneo que ya se esta jugando no se sostiene."""
        with pytest.raises(ValueError, match="comienza"):
            build_competition(enrollment_opens_at=datetime(2027, 6, 2, 9, 0))

    def test_opening_in_the_past_is_allowed(self):
        """Una fecha pasada quiere decir «abrela ya», y es legitimo."""
        competition = build_competition(enrollment_opens_at=datetime(2020, 1, 1, 9, 0))

        assert competition.enrollment_opens_at == datetime(2020, 1, 1, 9, 0)

    def test_moving_the_dates_cannot_strand_the_opening(self):
        """Adelantar el torneo por detras dejaria la apertura fuera de sitio."""
        competition = build_competition(enrollment_opens_at=datetime(2027, 5, 20, 9, 0))

        with pytest.raises(ValueError, match="comienza"):
            competition.update_info(dates=DateRange(date(2027, 5, 1), date(2027, 5, 3)))

    def test_scheduling_it_later_than_the_start_is_refused(self):
        competition = build_competition()

        with pytest.raises(ValueError, match="comienza"):
            competition.schedule_enrollment_opening(datetime(2027, 6, 2, 9, 0))

    def test_calling_it_off_is_always_fine(self):
        competition = build_competition(enrollment_opens_at=datetime(2027, 5, 20, 9, 0))

        competition.schedule_enrollment_opening(None)

        assert competition.enrollment_opens_at is None
