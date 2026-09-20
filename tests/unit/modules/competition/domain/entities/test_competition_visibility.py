"""Una competicion nace privada, y se abre al publico a proposito (BE #318).

Decidido el 20 sep: lo que hay hoy son Ryders entre amigos, asi que el valor
seguro es que nadie publique su torneo sin querer. Equivocarse hacia privado no
ensena nada a nadie; al reves, si.
"""

from datetime import date

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


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


class TestVisibilityOnTheCompetition:
    def test_it_is_born_private(self):
        """Sin decir nada, de nadie mas: es lo que hay hoy."""
        assert build_competition().visibility == Visibility.PRIVATE

    def test_it_can_be_born_public(self):
        competition = build_competition(visibility=Visibility.PUBLIC)

        assert competition.visibility == Visibility.PUBLIC

    def test_it_can_be_opened_up_later(self):
        competition = build_competition()

        competition.update_info(visibility=Visibility.PUBLIC)

        assert competition.visibility == Visibility.PUBLIC

    def test_it_can_be_closed_again(self):
        """Quien se arrepiente de haberlo publicado tiene que poder deshacerlo."""
        competition = build_competition(visibility=Visibility.PUBLIC)

        competition.update_info(visibility=Visibility.PRIVATE)

        assert competition.visibility == Visibility.PRIVATE

    def test_a_private_one_does_not_take_requests(self):
        assert build_competition().accepts_enrollment_requests() is False

    def test_a_public_one_does(self):
        assert build_competition(visibility=Visibility.PUBLIC).accepts_enrollment_requests() is True
