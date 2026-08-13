"""
Tests E2E del autocompletado de jugadores frente a cuentas desactivadas.

Recorren el camino real: un admin desactiva una cuenta por la API y otro
usuario la busca. Es la comprobación que importa, porque el filtro vive en el
repositorio y ningún test anterior llegaba hasta él desde el endpoint.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import create_admin_user, create_authenticated_user


async def set_account_active(
    client: AsyncClient, admin: dict, user_id: str, is_active: bool
) -> None:
    """Activa o desactiva una cuenta como administrador."""
    client.cookies.clear()
    client.cookies.update(admin["cookies"])
    response = await client.put(
        f"/api/v1/admin/users/{user_id}/active", json={"is_active": is_active}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    client.cookies.clear()


async def search_players(client: AsyncClient, searcher: dict, query: str) -> list[dict]:
    """Busca jugadores por nombre parcial con el autocompletado."""
    response = await client.get(
        "/api/v1/users/search-autocomplete",
        params={"query": query},
        cookies=searcher["cookies"],
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["users"]


class TestPlayerSearchExcludesInactiveAccounts:
    """El autocompletado de jugadores solo muestra cuentas activas."""

    @pytest.mark.asyncio
    async def test_deactivated_account_disappears_from_search(self, client: AsyncClient):
        """Una cuenta desactivada deja de aparecer en la búsqueda de jugadores."""
        searcher = await create_authenticated_user(
            client, "searcher@test.com", "P@ssw0rd123!", "Search", "Er"
        )
        target = await create_authenticated_user(
            client, "target@test.com", "P@ssw0rd123!", "Objetivo", "Desactivable"
        )
        admin = await create_admin_user(
            client, "search-admin@test.com", "P@ssw0rd123!", "Admin", "Test"
        )

        before = await search_players(client, searcher, "Desactivable")
        assert any(user["full_name"] == "Objetivo Desactivable" for user in before)

        await set_account_active(client, admin, target["user"]["id"], is_active=False)

        after = await search_players(client, searcher, "Desactivable")
        assert not any(user["full_name"] == "Objetivo Desactivable" for user in after)

    @pytest.mark.asyncio
    async def test_reactivated_account_comes_back(self, client: AsyncClient):
        """Volver a activar la cuenta la devuelve a la búsqueda."""
        searcher = await create_authenticated_user(
            client, "searcher2@test.com", "P@ssw0rd123!", "Search", "Er"
        )
        target = await create_authenticated_user(
            client, "target2@test.com", "P@ssw0rd123!", "Regreso", "Reactivable"
        )
        admin = await create_admin_user(
            client, "search-admin2@test.com", "P@ssw0rd123!", "Admin", "Test"
        )

        await set_account_active(client, admin, target["user"]["id"], is_active=False)
        await set_account_active(client, admin, target["user"]["id"], is_active=True)

        results = await search_players(client, searcher, "Reactivable")

        assert any(user["full_name"] == "Regreso Reactivable" for user in results)
