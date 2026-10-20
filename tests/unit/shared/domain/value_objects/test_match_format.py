"""Tests para MatchFormat enum."""

from src.shared.domain.value_objects.match_format import MatchFormat


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


class TestDefaultAllowance:
    """
    El porcentaje WHS por defecto de cada formato (RyderCupAM#165).

    Vivía dos veces, con sus constantes y su método, en `Round` y en `QuickMatch`.
    Ahora lo sabe el propio formato, y los dos lo preguntan aquí.
    """

    def test_singles_al_100(self):
        assert MatchFormat.SINGLES.default_allowance == 100

    def test_fourball_al_90(self):
        assert MatchFormat.FOURBALL.default_allowance == 90

    def test_foursomes_al_50(self):
        """Se aplica a la DIFERENCIA entre los dos bandos, no a cada jugador."""
        assert MatchFormat.FOURSOMES.default_allowance == 50

    def test_ningun_formato_se_queda_sin_porcentaje(self):
        """Un formato nuevo sin porcentaje rompe aquí, no al repartir golpes."""
        for formato in MatchFormat:
            assert isinstance(formato.default_allowance, int)
