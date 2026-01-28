"""
Tests de integración para endpoint GET /api/v1/users/me/roles/{competition_id}.

Valida que el endpoint retorna correctamente los roles del usuario actual
en una competición específica (admin, creator, player).
"""

from datetime import date
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

# Los value objects no son necesarios para estos tests (usamos el API)
from tests.integration.api.v1.helpers.auth_helper import create_and_login_user


# ======================================================================================
# TESTS: GET /api/v1/users/me/roles/{competition_id}
# ======================================================================================


@pytest.mark.skip(reason="Requires direct DB access to set is_admin=True (security limitation)")
@pytest.mark.asyncio
async def test_get_my_roles_returns_is_admin_true_for_admin_user(client: AsyncClient):
    """
    Given: Un usuario admin
    When: Consulta sus roles en una competición cualquiera
    Then: Retorna is_admin=True

    NOTE: Este test requiere acceso directo a la BD para crear un usuario admin,
    ya que no hay endpoint API para esto (limitación de seguridad intencional).
    Se debe implementar como fixture de BD o script de seed para tests.
    """
    pytest.skip("Admin creation requires direct database access")


@pytest.mark.asyncio
async def test_get_my_roles_returns_is_creator_true_for_creator(client: AsyncClient):
    """
    Given: Un usuario creador de una competición
    When: Consulta sus roles en su propia competición
    Then: Retorna is_creator=True, is_admin=False, is_player=False
    """
    # Crear y autenticar creator
    creator_user, creator_cookies = await create_and_login_user(
        client,
        email=f"creator_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Creator",
        last_name="User",
    )

    # Crear competición
    competition_data = {
        "name": "Creator Competition",
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "main_country": "ES",
        "team_1_name": "Europe",
        "team_2_name": "USA",
        "handicap_type": "PERCENTAGE",
        "handicap_percentage": 90,
        "max_players": 24,
        "team_assignment": "MANUAL",
    }

    comp_response = await client.post(
        "/api/v1/competitions",
        json=competition_data,
        cookies=creator_cookies,
    )
    assert comp_response.status_code == status.HTTP_201_CREATED
    competition_id = comp_response.json()["id"]

    # Creator consulta sus roles
    response = await client.get(
        f"/api/v1/users/me/roles/{competition_id}",
        cookies=creator_cookies,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["is_admin"] is False
    assert data["is_creator"] is True  # ← Creator de la competición
    assert data["is_player"] is False  # No está auto-enrollado
    assert data["competition_id"] == competition_id


@pytest.mark.asyncio
async def test_get_my_roles_returns_is_player_true_for_enrolled_user(client: AsyncClient):
    """
    Given: Un usuario enrollado (APPROVED) en una competición
    When: Consulta sus roles en esa competición
    Then: Retorna is_player=True, is_admin=False, is_creator=False
    """
    # Crear creator y su competición
    creator_user, creator_cookies = await create_and_login_user(
        client,
        email=f"creator_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Creator",
        last_name="User",
    )

    competition_data = {
        "name": "Player Competition",
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "main_country": "ES",
        "team_1_name": "Europe",
        "team_2_name": "USA",
        "handicap_type": "PERCENTAGE",
        "handicap_percentage": 90,
        "max_players": 24,
        "team_assignment": "MANUAL",
    }

    comp_response = await client.post(
        "/api/v1/competitions",
        json=competition_data,
        cookies=creator_cookies,
    )
    assert comp_response.status_code == status.HTTP_201_CREATED
    competition_id = comp_response.json()["id"]

    # Activar competición (para permitir enrollments)
    await client.post(
        f"/api/v1/competitions/{competition_id}/activate",
        cookies=creator_cookies,
    )

    # Crear player y solicitar enrollment
    player_user, player_cookies = await create_and_login_user(
        client,
        email=f"player_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Player",
        last_name="User",
    )

    enroll_response = await client.post(
        f"/api/v1/competitions/{competition_id}/enrollments",
        json={"type": "REQUEST"},
        cookies=player_cookies,
    )
    assert enroll_response.status_code == status.HTTP_201_CREATED
    enrollment_id = enroll_response.json()["id"]

    # Creator aprueba el enrollment
    await client.post(
        f"/api/v1/enrollments/{enrollment_id}/approve",
        cookies=creator_cookies,
    )

    # Player consulta sus roles (debe ser PLAYER ahora)
    response = await client.get(
        f"/api/v1/users/me/roles/{competition_id}",
        cookies=player_cookies,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["is_admin"] is False
    assert data["is_creator"] is False
    assert data["is_player"] is True  # ← Enrollado con APPROVED
    assert data["competition_id"] == competition_id


@pytest.mark.asyncio
async def test_get_my_roles_all_false_for_unrelated_user(client: AsyncClient):
    """
    Given: Un usuario que NO es admin, NI creator, NI player
    When: Consulta sus roles en una competición ajena
    Then: Retorna todos los flags en False
    """
    # Crear creator y su competición
    creator_user, creator_cookies = await create_and_login_user(
        client,
        email=f"creator_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Creator",
        last_name="User",
    )

    competition_data = {
        "name": "Test Competition",
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "main_country": "ES",
        "team_1_name": "Europe",
        "team_2_name": "USA",
        "handicap_type": "PERCENTAGE",
        "handicap_percentage": 90,
        "max_players": 24,
        "team_assignment": "MANUAL",
    }

    comp_response = await client.post(
        "/api/v1/competitions",
        json=competition_data,
        cookies=creator_cookies,
    )
    assert comp_response.status_code == status.HTTP_201_CREATED
    competition_id = comp_response.json()["id"]

    # Crear usuario sin relación con la competición
    unrelated_user, unrelated_cookies = await create_and_login_user(
        client,
        email=f"unrelated_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Unrelated",
        last_name="User",
    )

    # Consultar roles (debería ser todo False)
    response = await client.get(
        f"/api/v1/users/me/roles/{competition_id}",
        cookies=unrelated_cookies,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["is_admin"] is False
    assert data["is_creator"] is False
    assert data["is_player"] is False
    assert data["competition_id"] == competition_id


@pytest.mark.asyncio
async def test_get_my_roles_creator_can_also_be_player(client: AsyncClient):
    """
    Given: Un usuario creador que se enrolla en su propia competición
    When: Consulta sus roles
    Then: Retorna is_creator=True Y is_player=True simultáneamente
    """
    # Crear creator y su competición
    creator_user, creator_cookies = await create_and_login_user(
        client,
        email=f"creator_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Creator",
        last_name="User",
    )

    competition_data = {
        "name": "Creator as Player",
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "main_country": "ES",
        "team_1_name": "Europe",
        "team_2_name": "USA",
        "handicap_type": "PERCENTAGE",
        "handicap_percentage": 90,
        "max_players": 24,
        "team_assignment": "MANUAL",
    }

    comp_response = await client.post(
        "/api/v1/competitions",
        json=competition_data,
        cookies=creator_cookies,
    )
    assert comp_response.status_code == status.HTTP_201_CREATED
    competition_id = comp_response.json()["id"]

    # Activar competición
    await client.post(
        f"/api/v1/competitions/{competition_id}/activate",
        cookies=creator_cookies,
    )

    # Creator se enrolla en su propia competición (enrollment directo)
    enroll_response = await client.post(
        f"/api/v1/competitions/{competition_id}/enrollments",
        json={"type": "DIRECT"},
        cookies=creator_cookies,
    )
    assert enroll_response.status_code == status.HTTP_201_CREATED

    # Consultar roles (debe ser CREATOR + PLAYER)
    response = await client.get(
        f"/api/v1/users/me/roles/{competition_id}",
        cookies=creator_cookies,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["is_admin"] is False
    assert data["is_creator"] is True  # ← Creó la competición
    assert data["is_player"] is True  # ← También está enrollado
    assert data["competition_id"] == competition_id


@pytest.mark.asyncio
async def test_get_my_roles_returns_404_for_nonexistent_competition(client: AsyncClient):
    """
    Given: Un usuario autenticado
    When: Consulta roles en una competición que NO existe
    Then: Retorna 404 Not Found
    """
    # Crear usuario
    user, user_cookies = await create_and_login_user(
        client,
        email=f"user_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Test",
        last_name="User",
    )

    # Consultar competición inexistente
    fake_competition_id = str(uuid4())
    response = await client.get(
        f"/api/v1/users/me/roles/{fake_competition_id}",
        cookies=user_cookies,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_my_roles_returns_401_for_unauthenticated_user(client: AsyncClient):
    """
    Given: Un usuario NO autenticado (sin cookies)
    When: Consulta roles en una competición
    Then: Retorna 401 Unauthorized
    """
    fake_competition_id = str(uuid4())
    response = await client.get(f"/api/v1/users/me/roles/{fake_competition_id}")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_my_roles_returns_400_for_invalid_competition_id_format(client: AsyncClient):
    """
    Given: Un usuario autenticado
    When: Consulta roles con un competition_id con formato inválido (no UUID)
    Then: Retorna 400 Bad Request (o 422 Unprocessable Entity por FastAPI)
    """
    # Crear usuario
    user, user_cookies = await create_and_login_user(
        client,
        email=f"user_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name="Test",
        last_name="User",
    )

    # Consultar con ID inválido
    response = await client.get(
        "/api/v1/users/me/roles/invalid-uuid-format",
        cookies=user_cookies,
    )

    # FastAPI valida path parameters automáticamente y retorna 422
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
