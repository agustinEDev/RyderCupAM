"""Tests del cupo de jugadores de Competition.

El cupo es un invariante del dominio: se valida en el constructor y en cada
`update_info`, así que vale para cualquier competición sin importar su tipo.
Aquí se fijan sus dos extremos y su valor por defecto.
"""

from datetime import date

import pytest

from src.modules.competition.domain.entities.competition import (
    MAX_PLAYERS,
    MIN_PLAYERS,
    Competition,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


def build_competition(**overrides) -> Competition:
    """Competición en DRAFT, con lo mínimo para poder mirarle el cupo."""
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


class TestMaxPlayersConstants:
    """Los dos números que definen el rango."""

    def test_minimum_is_two(self):
        """Dos jugadores es lo mínimo con lo que hay partido."""
        assert MIN_PLAYERS == 2

    def test_maximum_is_one_hundred(self):
        """100 mientras las inscripciones no se paginen: más arriba se truncan."""
        assert MAX_PLAYERS == 100


class TestMaxPlayersOnConstruction:
    """El cupo se valida al construir."""

    def test_accepts_the_cap(self):
        assert build_competition(max_players=100).max_players == 100

    def test_rejects_one_above_the_cap(self):
        with pytest.raises(ValueError, match="entre 2 y 100"):
            build_competition(max_players=101)

    def test_accepts_the_minimum(self):
        assert build_competition(max_players=2).max_players == 2

    def test_rejects_one_below_the_minimum(self):
        with pytest.raises(ValueError, match="entre 2 y 100"):
            build_competition(max_players=1)

    def test_defaults_to_twelve(self):
        """Sin decir nada, 12: una Ryder entre amigos son 12 jugadores."""
        assert build_competition().max_players == 12


class TestMaxPlayersOnCreate:
    """El factory `create` tiene su propio valor por defecto, y debe coincidir."""

    def test_create_defaults_to_twelve(self):
        competition = Competition.create(
            id=CompetitionId.generate(),
            creator_id=UserId(str(CompetitionId.generate().value)),
            name=CompetitionName("Ryder Cup Madrid 2026"),
            dates=DateRange(date(2026, 6, 1), date(2026, 6, 3)),
            location=Location(CountryCode("ES")),
            team_1_name="Europe",
            team_2_name="USA",
            play_mode=PlayMode.HANDICAP,
        )

        assert competition.max_players == 12


class TestMaxPlayersOnUpdate:
    """El mismo rango se aplica al editar, no solo al crear."""

    def test_accepts_the_cap(self):
        competition = build_competition(max_players=12)

        competition.update_info(max_players=100)

        assert competition.max_players == 100

    def test_rejects_one_above_the_cap(self):
        competition = build_competition(max_players=12)

        with pytest.raises(ValueError, match="entre 2 y 100"):
            competition.update_info(max_players=101)

        assert competition.max_players == 12

    def test_rejects_one_below_the_minimum(self):
        competition = build_competition(max_players=12)

        with pytest.raises(ValueError, match="entre 2 y 100"):
            competition.update_info(max_players=1)

        assert competition.max_players == 12

    def test_none_leaves_the_cap_untouched(self):
        """`None` significa «no lo toques»: es lo que llega en una edición parcial."""
        competition = build_competition(max_players=12)

        competition.update_info(name=CompetitionName("Otro nombre"))

        assert competition.max_players == 12
