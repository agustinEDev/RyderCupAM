"""De donde sale la zona horaria de una competicion (BE #319).

Del campo donde se juega, y del primero si hay varios: la hora de apertura que
escribe el organizador es local de alli.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class CampoFalso:
    """Un campo de golf del que solo importa su zona."""

    def __init__(self, timezone: str | None):
        self.timezone = timezone


class RepositorioFalso:
    """Devuelve el campo que se le diga, por id."""

    def __init__(self, campos: dict):
        self._campos = campos

    async def find_by_id(self, golf_course_id):
        return self._campos.get(golf_course_id)


def build_competition() -> Competition:
    return Competition(
        id=CompetitionId.generate(),
        creator_id=UserId(str(CompetitionId.generate().value)),
        name=CompetitionName("Ryder Cup Madrid 2026"),
        dates=DateRange(date(2026, 6, 1), date(2026, 6, 3)),
        location=Location(CountryCode("ES")),
        team_1_name="Europe",
        team_2_name="USA",
        play_mode=PlayMode.HANDICAP,
    )


class TestTheZoneOfACompetition:
    async def test_without_a_course_there_is_no_zone(self):
        """Se puede crear, invitar y anadir el campo despues (BE #323)."""
        resolutor = CompetitionTimezoneFromCourse(RepositorioFalso({}))

        assert await resolutor.for_competition(build_competition()) is None

    async def test_it_is_the_zone_of_the_course(self):
        competition = build_competition()
        campo_id = GolfCourseId.generate()
        competition.add_golf_course(campo_id, CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(
            RepositorioFalso({campo_id: CampoFalso("Atlantic/Canary")})
        )

        assert await resolutor.for_competition(competition) == "Atlantic/Canary"

    async def test_with_several_it_is_the_first_one_played(self):
        """El orden es el que se juega, no el que se aparece en la base."""
        competition = build_competition()
        primero, segundo = GolfCourseId.generate(), GolfCourseId.generate()
        competition.add_golf_course(primero, CountryCode("ES"))
        competition.add_golf_course(segundo, CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(
            RepositorioFalso(
                {primero: CampoFalso("Europe/Madrid"), segundo: CampoFalso("Atlantic/Canary")}
            )
        )

        assert await resolutor.for_competition(competition) == "Europe/Madrid"

    async def test_a_course_without_a_zone_gives_none(self):
        """Un campo sin coordenadas no tiene zona, y no se inventa."""
        competition = build_competition()
        campo_id = GolfCourseId.generate()
        competition.add_golf_course(campo_id, CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(RepositorioFalso({campo_id: CampoFalso(None)}))

        assert await resolutor.for_competition(competition) is None

    async def test_a_course_that_is_not_there_does_not_bring_anything_down(self):
        """Apuntar a un campo que ya no existe se avisa, no se revienta."""
        competition = build_competition()
        competition.add_golf_course(GolfCourseId.generate(), CountryCode("ES"))
        resolutor = CompetitionTimezoneFromCourse(RepositorioFalso({}))

        assert await resolutor.for_competition(competition) is None
