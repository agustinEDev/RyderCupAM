"""Que se pueda corregir el montaje mientras las inscripciones estan abiertas.

Antes solo se podia tocar en DRAFT. Con la invitacion abriendo el torneo
(BE #319), dejarlo ahi convertia invitar en una puerta de un solo sentido:
quien invitaba a un amigo antes de poner el campo de golf ya no podia ponerlo
nunca, y sin campo no hay rondas que crear. La unica salida era cancelar y
volver a empezar (BE #323).

De CLOSED en adelante sigue cerrado: ahi ya se sortean equipos y se generan
partidos.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import (
    Competition,
    CompetitionStateError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


def build_competition(**overrides) -> Competition:
    """Competicion con lo minimo; por defecto en DRAFT."""
    argumentos = {
        "id": CompetitionId.generate(),
        "creator_id": UserId(str(CompetitionId.generate().value)),
        "name": CompetitionName("Ryder Cup Madrid 2026"),
        "dates": DateRange(date(2026, 6, 1), date(2026, 6, 3)),
        "location": Location(CountryCode("ES")),
        "team_1_name": "Europe",
        "team_2_name": "USA",
        "play_mode": PlayMode.HANDICAP,
    }
    argumentos.update(overrides)
    return Competition(**argumentos)


def open_competition(**overrides) -> Competition:
    """Competicion con las inscripciones abiertas (ACTIVE)."""
    competition = build_competition(**overrides)
    competition.activate()
    return competition


class TestEditingWhileEnrollmentIsOpen:
    """La configuracion se puede corregir mientras hay inscripciones abiertas."""

    def test_allows_modifications_when_open(self):
        assert open_competition().allows_modifications() is True

    def test_the_name_can_be_fixed(self):
        competition = open_competition()

        competition.update_info(name=CompetitionName("Ryder de los amigos"))

        assert str(competition.name) == "Ryder De Los Amigos"

    def test_the_cap_can_be_fixed(self):
        competition = open_competition(max_players=12)

        competition.update_info(max_players=24)

        assert competition.max_players == 24

    def test_once_enrollment_closes_it_is_closed(self):
        competition = open_competition()
        competition.close_enrollments()

        with pytest.raises(CompetitionStateError):
            competition.update_info(name=CompetitionName("Ya no"))


class TestGolfCoursesWhileEnrollmentIsOpen:
    """Los campos son justo lo que faltaba poner: se pueden tocar igual."""

    def test_a_course_can_be_added_when_open(self):
        competition = open_competition()

        competition.add_golf_course(GolfCourseId.generate(), CountryCode("ES"))

        assert len(competition.golf_courses) == 1

    def test_a_course_can_be_removed_when_open(self):
        competition = open_competition()
        course_id = GolfCourseId.generate()
        competition.add_golf_course(course_id, CountryCode("ES"))

        competition.remove_golf_course(course_id)

        assert competition.golf_courses == []

    def test_courses_can_be_reordered_when_open(self):
        competition = open_competition()
        primero = GolfCourseId.generate()
        segundo = GolfCourseId.generate()
        competition.add_golf_course(primero, CountryCode("ES"))
        competition.add_golf_course(segundo, CountryCode("ES"))

        competition.reorder_golf_courses([(segundo, 1), (primero, 2)])

        assert [c.golf_course_id for c in competition.golf_courses] == [segundo, primero]

    @pytest.mark.parametrize(
        "status",
        [
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
            CompetitionStatus.COMPLETED,
            CompetitionStatus.CANCELLED,
        ],
    )
    def test_no_courses_once_enrollment_closes(self, status):
        competition = build_competition(status=status)

        with pytest.raises(CompetitionStateError):
            competition.add_golf_course(GolfCourseId.generate(), CountryCode("ES"))
