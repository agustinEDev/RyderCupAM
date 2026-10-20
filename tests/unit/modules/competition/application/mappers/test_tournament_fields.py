"""
Los campos del tipo y de la Ryder en las respuestas, de un solo sitio (#251).

Se construían a mano en tres sitios (la ficha, la respuesta de crear y la de
editar), y los tres leían la pieza de la Ryder suponiendo que siempre existe.
"""

from datetime import date

from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode


def _competicion(**extra) -> Competition:
    return Competition.create(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Torneo del club"),
        dates=DateRange(date(2030, 6, 1), date(2030, 6, 2)),
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        **extra,
    )


def test_una_ryder_cup_lleva_su_tipo_su_modalidad_y_sus_equipos():
    campos = CompetitionDTOMapper.tournament_fields(
        _competicion(team_1_name="Europa", team_2_name="América")
    )

    assert campos["tournament_type"] == "RYDER_CUP"
    assert campos["modality"] == "MATCH_PLAY"
    assert (campos["team_1_name"], campos["team_2_name"]) == ("Europa", "América")
    assert campos["team_assignment"] == "MANUAL"
    assert campos["setup_mode"] == "RYDER_CUP"
    assert campos["team_a_captain_id"] is None


def test_un_stableford_lleva_su_tipo_y_nada_de_la_ryder():
    campos = CompetitionDTOMapper.tournament_fields(
        _competicion(tournament_type=TournamentType.STABLEFORD)
    )

    assert campos["tournament_type"] == "STABLEFORD"
    assert campos["modality"] == "STROKE_PLAY"
    for campo in (
        "team_1_name",
        "team_2_name",
        "team_assignment",
        "setup_mode",
        "team_a_captain_id",
        "team_b_captain_id",
        "team_a_vice_captain_id",
        "team_b_vice_captain_id",
    ):
        assert campos[campo] is None, campo
