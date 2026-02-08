"""Tests para MatchFormat enum."""

from src.modules.competition.domain.value_objects.match_format import MatchFormat


class TestMatchFormat:
    """Tests para MatchFormat"""

    def test_has_all_expected_values(self):
        """Verifica que existen todos los valores esperados."""
        assert MatchFormat.SINGLES.value == "SINGLES"
        assert MatchFormat.FOURBALL.value == "FOURBALL"
        assert MatchFormat.FOURSOMES.value == "FOURSOMES"

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(MatchFormat.SINGLES) == "SINGLES"
        assert str(MatchFormat.FOURBALL) == "FOURBALL"

    def test_players_per_team_singles(self):
        """SINGLES tiene 1 jugador por equipo."""
        assert MatchFormat.SINGLES.players_per_team() == 1

    def test_players_per_team_fourball(self):
        """FOURBALL tiene 2 jugadores por equipo."""
        assert MatchFormat.FOURBALL.players_per_team() == 2

    def test_players_per_team_foursomes(self):
        """FOURSOMES tiene 2 jugadores por equipo."""
        assert MatchFormat.FOURSOMES.players_per_team() == 2

    def test_is_string_subclass(self):
        """Es subclase de str."""
        assert isinstance(MatchFormat.SINGLES, str)
