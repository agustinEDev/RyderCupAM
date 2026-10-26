"""
Tests E2E: quien busca jugadores no se encuentra a sí mismo (FE #938, 26 oct 2026).

Al añadir amigos o invitar a una competición salía uno mismo entre los
resultados, y ocupaba uno de los 10 huecos del autocompletado.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import create_authenticated_user


@pytest.mark.asyncio
async def test_search_own_surname_returns_only_the_others(client: AsyncClient):
    """
    GIVEN: Dos jugadores que comparten apellido
    WHEN: Uno de ellos busca ese apellido
    THEN: Sale el otro, y él no
    """
    searcher = await create_authenticated_user(client, "me@test.com", "P@ssw0rd123!", "Yo", "Mismo")
    await create_authenticated_user(client, "other@test.com", "P@ssw0rd123!", "Otro", "Mismo")

    response = await client.get(
        "/api/v1/users/search-autocomplete",
        params={"query": "Mismo"},
        cookies=searcher["cookies"],
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert [user["full_name"] for user in response.json()["users"]] == ["Otro Mismo"]
