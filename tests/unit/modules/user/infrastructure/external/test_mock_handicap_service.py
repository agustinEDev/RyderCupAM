"""
Tests for MockHandicapService
"""

import pytest

from src.modules.user.infrastructure.external.mock_handicap_service import MockHandicapService


class TestMockHandicapServiceBasicUsage:
    """Tests básicos para MockHandicapService."""

    @pytest.mark.asyncio
    async def test_search_handicap_returns_default_value(self):
        """Test: Buscar hándicap devuelve el valor por defecto."""
        service = MockHandicapService(default=15.0)

        handicap = await service.search_handicap("Any Name")

        assert handicap == 15.0

    @pytest.mark.asyncio
    async def test_search_handicap_returns_configured_value(self):
        """Test: Buscar hándicap devuelve valor configurado para nombre específico."""
        handicaps = {
            "Rafael Nadal Parera": 2.5,
            "Carlos Alcaraz Garfia": 5.0
        }
        service = MockHandicapService(handicaps=handicaps)

        nadal_handicap = await service.search_handicap("Rafael Nadal Parera")
        alcaraz_handicap = await service.search_handicap("Carlos Alcaraz Garfia")

        assert nadal_handicap == 2.5
        assert alcaraz_handicap == 5.0

    @pytest.mark.asyncio
    async def test_search_handicap_returns_default_for_unknown_name(self):
        """Test: Buscar nombre no configurado devuelve valor por defecto."""
        handicaps = {"Rafael Nadal Parera": 2.5}
        service = MockHandicapService(handicaps=handicaps, default=20.0)

        handicap = await service.search_handicap("Unknown Player")

        assert handicap == 20.0

    @pytest.mark.asyncio
    async def test_search_handicap_with_none_default(self):
        """Test: Configurar default=None devuelve None para nombres no encontrados."""
        service = MockHandicapService(default=None)

        handicap = await service.search_handicap("Unknown Player")

        assert handicap is None

    @pytest.mark.asyncio
    async def test_search_handicap_with_empty_name(self):
        """Test: Buscar con nombre vacío devuelve default."""
        service = MockHandicapService(default=15.0)

        handicap = await service.search_handicap("")

        assert handicap == 15.0


class TestMockHandicapServiceConfiguration:
    """Tests para diferentes configuraciones del servicio mock."""

    @pytest.mark.asyncio
    async def test_create_with_no_handicaps_dict(self):
        """Test: Crear servicio sin diccionario de hándicaps."""
        service = MockHandicapService(default=18.0)

        handicap = await service.search_handicap("Any Name")

        assert handicap == 18.0

    @pytest.mark.asyncio
    async def test_create_with_empty_handicaps_dict(self):
        """Test: Crear servicio con diccionario vacío."""
        service = MockHandicapService(handicaps={}, default=25.0)

        handicap = await service.search_handicap("Any Name")

        assert handicap == 25.0

    @pytest.mark.asyncio
    async def test_create_with_multiple_players(self):
        """Test: Configurar múltiples jugadores con diferentes hándicaps."""
        handicaps = {
            "Rafael Nadal Parera": 2.5,
            "Carlos Alcaraz Garfia": 5.0,
            "Jon Rahm Rodriguez": 3.2,
            "Sergio Garcia Fernandez": 4.8
        }
        service = MockHandicapService(handicaps=handicaps)

        assert await service.search_handicap("Rafael Nadal Parera") == 2.5
        assert await service.search_handicap("Carlos Alcaraz Garfia") == 5.0
        assert await service.search_handicap("Jon Rahm Rodriguez") == 3.2
        assert await service.search_handicap("Sergio Garcia Fernandez") == 4.8

    @pytest.mark.asyncio
    async def test_handicap_with_zero_value(self):
        """Test: Configurar hándicap con valor cero."""
        handicaps = {"Scratch Player": 0.0}
        service = MockHandicapService(handicaps=handicaps)

        handicap = await service.search_handicap("Scratch Player")

        assert handicap == 0.0

    @pytest.mark.asyncio
    async def test_handicap_with_negative_value(self):
        """Test: Configurar hándicap con valor negativo."""
        handicaps = {"Pro Player": -2.5}
        service = MockHandicapService(handicaps=handicaps)

        handicap = await service.search_handicap("Pro Player")

        assert handicap == -2.5


class TestMockHandicapServiceCaseSensitivity:
    """Tests para verificar sensibilidad a mayúsculas/minúsculas."""

    @pytest.mark.asyncio
    async def test_search_is_case_sensitive(self):
        """Test: La búsqueda es sensible a mayúsculas/minúsculas."""
        handicaps = {"Rafael Nadal Parera": 2.5}
        service = MockHandicapService(handicaps=handicaps, default=None)

        exact_match = await service.search_handicap("Rafael Nadal Parera")
        wrong_case = await service.search_handicap("rafael nadal parera")

        assert exact_match == 2.5
        assert wrong_case is None  # No encuentra por diferencia de mayúsculas

    @pytest.mark.asyncio
    async def test_search_with_extra_spaces(self):
        """Test: Espacios extra afectan la búsqueda."""
        handicaps = {"Rafael Nadal Parera": 2.5}
        service = MockHandicapService(handicaps=handicaps, default=None)

        exact_match = await service.search_handicap("Rafael Nadal Parera")
        with_spaces = await service.search_handicap("Rafael  Nadal  Parera")

        assert exact_match == 2.5
        assert with_spaces is None  # No encuentra por espacios extra


class TestMockHandicapServiceForTesting:
    """Tests para verificar utilidad del mock en escenarios de testing."""

    @pytest.mark.asyncio
    async def test_mock_service_is_deterministic(self):
        """Test: El servicio mock devuelve siempre el mismo valor."""
        service = MockHandicapService(default=15.0)

        result1 = await service.search_handicap("Test Player")
        result2 = await service.search_handicap("Test Player")
        result3 = await service.search_handicap("Test Player")

        assert result1 == result2 == result3 == 15.0

    @pytest.mark.asyncio
    async def test_mock_service_no_external_calls(self):
        """Test: El servicio mock no hace llamadas externas (es instantáneo)."""
        import time
        service = MockHandicapService(default=15.0)

        start = time.time()
        await service.search_handicap("Test Player")
        elapsed = time.time() - start

        # Debe ser casi instantáneo (< 10ms)
        assert elapsed < 0.01

    @pytest.mark.asyncio
    async def test_mock_service_allows_testing_edge_cases(self):
        """Test: El mock permite probar casos extremos fácilmente."""
        # Configurar casos extremos
        handicaps = {
            "Min Handicap": -10.0,  # Mínimo válido
            "Max Handicap": 54.0,   # Máximo válido
            "Zero Handicap": 0.0,   # Cero
            "No Handicap": None     # Sin hándicap
        }
        service = MockHandicapService(handicaps=handicaps, default=None)

        assert await service.search_handicap("Min Handicap") == -10.0
        assert await service.search_handicap("Max Handicap") == 54.0
        assert await service.search_handicap("Zero Handicap") == 0.0
        # Note: None in dict will use dict value, not default
        assert handicaps["No Handicap"] is None


class TestMockHandicapServiceRealWorldScenarios:
    """Tests con escenarios del mundo real usando nombres de la RFEG."""

    @pytest.mark.asyncio
    async def test_search_real_player_names(self):
        """Test: Buscar jugadores reales configurados en el mock."""
        # Configurar con nombres reales de la RFEG
        handicaps = {
            "Rafael Nadal Parera": 2.5,
            "Carlos Alcaraz Garfia": 5.0
        }
        service = MockHandicapService(handicaps=handicaps)

        nadal = await service.search_handicap("Rafael Nadal Parera")
        alcaraz = await service.search_handicap("Carlos Alcaraz Garfia")

        assert nadal == 2.5
        assert alcaraz == 5.0

    @pytest.mark.asyncio
    async def test_tournament_scenario_multiple_players(self):
        """Test: Escenario de torneo con múltiples jugadores."""
        # Simular hándicaps de jugadores para un torneo
        tournament_players = {
            "Rafael Nadal Parera": 2.5,
            "Carlos Alcaraz Garfia": 5.0,
            "Amateur Player 1": 15.0,
            "Amateur Player 2": 20.5,
            "Amateur Player 3": 18.0
        }
        service = MockHandicapService(handicaps=tournament_players)

        # Verificar que todos los jugadores tienen hándicap
        for player_name in tournament_players:
            handicap = await service.search_handicap(player_name)
            assert handicap == tournament_players[player_name]

    @pytest.mark.asyncio
    async def test_new_player_gets_default_handicap(self):
        """Test: Jugador nuevo recibe hándicap por defecto."""
        existing_players = {
            "Rafael Nadal Parera": 2.5,
            "Carlos Alcaraz Garfia": 5.0
        }
        default_new_player_handicap = 28.0
        service = MockHandicapService(
            handicaps=existing_players,
            default=default_new_player_handicap
        )

        new_player_handicap = await service.search_handicap("New Player Name")

        assert new_player_handicap == default_new_player_handicap
