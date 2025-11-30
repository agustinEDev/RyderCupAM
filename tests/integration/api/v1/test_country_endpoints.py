"""
Tests E2E para Country Endpoints.

Tests de integración que verifican los endpoints de países y adyacencias.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user


class TestListCountries:
    """Tests para GET /api/v1/countries"""

    @pytest.mark.asyncio
    async def test_list_countries_returns_list(self, client: AsyncClient):
        """Listar países retorna lista no vacía."""
        user = await create_authenticated_user(
            client, "user@test.com", "Pass123!", "Test", "User"
        )

        response = await client.get(
            "/api/v1/countries",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Debería haber países (seed data tiene 166)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_list_countries_structure(self, client: AsyncClient):
        """Países tienen estructura correcta."""
        user = await create_authenticated_user(
            client, "user2@test.com", "Pass123!", "Test", "Two"
        )

        response = await client.get(
            "/api/v1/countries",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verificar estructura del primer país
        if len(data) > 0:
            country = data[0]
            assert "code" in country
            assert "name_en" in country
            assert "name_es" in country
            assert len(country["code"]) == 2  # ISO alpha-2

    @pytest.mark.asyncio
    async def test_list_countries_includes_spain(self, client: AsyncClient):
        """Lista de países incluye España."""
        user = await create_authenticated_user(
            client, "user3@test.com", "Pass123!", "Test", "Three"
        )

        response = await client.get(
            "/api/v1/countries",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        spain = next((c for c in data if c["code"] == "ES"), None)
        assert spain is not None
        assert spain["name_en"] == "Spain"
        assert spain["name_es"] == "España"


class TestListAdjacentCountries:
    """Tests para GET /api/v1/countries/{code}/adjacent"""

    @pytest.mark.asyncio
    async def test_adjacent_countries_spain(self, client: AsyncClient):
        """España tiene países adyacentes."""
        user = await create_authenticated_user(
            client, "user4@test.com", "Pass123!", "Test", "Four"
        )

        response = await client.get(
            "/api/v1/countries/ES/adjacent",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # España tiene frontera con Portugal y Francia
        codes = [c["code"] for c in data]
        assert "PT" in codes or "FR" in codes

    @pytest.mark.asyncio
    async def test_adjacent_countries_invalid_code_returns_400(self, client: AsyncClient):
        """Código de país inválido retorna 400."""
        user = await create_authenticated_user(
            client, "user5@test.com", "Pass123!", "Test", "Five"
        )

        response = await client.get(
            "/api/v1/countries/INVALID/adjacent",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_adjacent_countries_not_found_returns_404(self, client: AsyncClient):
        """País no existente retorna 404."""
        user = await create_authenticated_user(
            client, "user6@test.com", "Pass123!", "Test", "Six"
        )

        response = await client.get(
            "/api/v1/countries/XX/adjacent",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_adjacent_countries_structure(self, client: AsyncClient):
        """Países adyacentes tienen estructura correcta."""
        user = await create_authenticated_user(
            client, "user7@test.com", "Pass123!", "Test", "Seven"
        )

        response = await client.get(
            "/api/v1/countries/FR/adjacent",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        if len(data) > 0:
            country = data[0]
            assert "code" in country
            assert "name_en" in country
            assert "name_es" in country
