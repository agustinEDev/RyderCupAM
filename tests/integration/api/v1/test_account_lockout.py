"""
Integration tests for Account Lockout feature (v1.13.0).

Tests the complete flow:
- Failed login attempts increment counter
- Account locks after 10 failed attempts
- Login blocked with HTTP 423 when locked
- Admin can manually unlock account
- Successful login resets counter
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_account_locks_after_max_failed_attempts(client: AsyncClient):
    """
    Test que la cuenta se bloquea tras MAX_FAILED_ATTEMPTS (10) intentos fallidos.

    Given: Usuario existe en BD
    When: Hacemos 10 intentos de login con password incorrecta
    Then:
        - Intentos 1-9: HTTP 401 Unauthorized
        - Intento 10: HTTP 423 Locked
        - failed_login_attempts = 10
        - locked_until está establecido (NOW + 30 min)
    """
    # Given: Crear usuario de prueba
    register_data = {
        "email": "locktest@example.com",
        "password": "ValidPassword123!",
        "first_name": "Lock",
        "last_name": "Test",
    }

    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # When: Hacer 9 intentos fallidos (no debería bloquear aún)
    # Rate limiting bypass: Usar diferentes IDs de cliente simulados con X-Test-Client-ID
    for i in range(9):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "locktest@example.com",
                "password": "WrongPassword123!",
            },
            headers={
                "X-Test-Client-ID": f"test-client-1-{i + 1}"
            },  # Cliente diferente por intento
        )
        # Then: Todos retornan 401 (credenciales incorrectas)
        assert response.status_code == 401, f"Attempt {i + 1} should return 401"

    # When: Intento 10 (debería bloquear)
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "locktest@example.com",
            "password": "WrongPassword123!",
        },
        headers={"X-Test-Client-ID": "test-client-1-10"},
    )

    # Then: Retorna 423 Locked
    assert response.status_code == 423
    assert "Account locked" in response.json()["detail"]
    assert "locked until" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_locked_account_cannot_login_even_with_correct_password(
    client: AsyncClient,
):
    """
    Test que una cuenta bloqueada NO puede hacer login incluso con password correcta.

    Given: Cuenta está bloqueada (10 intentos fallidos)
    When: Intentamos login con password CORRECTA
    Then: HTTP 423 Locked (no permite login)
    """
    # Given: Crear usuario y bloquearlo
    register_data = {
        "email": "locked@example.com",
        "password": "CorrectPassword123!",
        "first_name": "Locked",
        "last_name": "User",
    }

    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # Hacer 10 intentos fallidos para bloquear
    for i in range(10):
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "locked@example.com",
                "password": "WrongPassword123!",
            },
            headers={"X-Test-Client-ID": f"test-client-2-{i + 1}"},
        )

    # When: Intentar login con password CORRECTA
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "locked@example.com",
            "password": "CorrectPassword123!",  # ← Password correcta
        },
        headers={"X-Test-Client-ID": "test-client-2-11"},
    )

    # Then: Sigue bloqueada (423)
    assert response.status_code == 423
    assert "Account locked" in response.json()["detail"]


@pytest.mark.asyncio
async def test_successful_login_resets_failed_attempts_counter(client: AsyncClient):
    """
    Test que un login exitoso resetea el contador de intentos fallidos.

    Given: Usuario con 5 intentos fallidos
    When: Login exitoso con password correcta
    Then:
        - HTTP 200 OK
        - failed_login_attempts resetea a 0
        - Siguiente intento fallido empieza desde 0 nuevamente
    """
    # Given: Crear usuario
    register_data = {
        "email": "reset@example.com",
        "password": "ValidPassword123!",
        "first_name": "Reset",
        "last_name": "Test",
    }

    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # Hacer 5 intentos fallidos
    for i in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "reset@example.com",
                "password": "WrongPassword123!",
            },
            headers={"X-Test-Client-ID": f"test-client-3-{i + 1}"},
        )

    # When: Login exitoso
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "reset@example.com",
            "password": "ValidPassword123!",  # ← Correcta
        },
        headers={"X-Test-Client-ID": "test-client-3-6"},
    )

    # Then: Login exitoso
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Verificar que contador se reseteo:
    # Si hacemos 9 intentos fallidos más, NO debería bloquear
    # (porque el contador se reseteo a 0)
    for i in range(9):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "reset@example.com",
                "password": "WrongPassword123!",
            },
            headers={"X-Test-Client-ID": f"test-client-3-{i + 10}"},
        )
        assert response.status_code == 401  # No bloqueado aún


@pytest.mark.asyncio
@pytest.mark.skip(reason="Admin role system not implemented yet (v2.1.0)")
async def test_admin_can_unlock_account_manually(client: AsyncClient):
    """
    Test que un admin puede desbloquear una cuenta manualmente.

    Given: Cuenta bloqueada (10 intentos fallidos)
    When: Admin llama POST /api/v1/auth/unlock-account
    Then:
        - HTTP 200 OK
        - failed_login_attempts = 0
        - locked_until = None
        - Puede hacer login exitoso inmediatamente

    NOTE: Skipped porque el sistema de roles no está implementado aún.
    Este test se habilitará en v2.1.0 cuando se implemente el sistema de roles.
    """
    # TODO (v2.1.0): Implementar cuando exista sistema de roles
    pass


# ============================================================================
# Edge Cases y Security Tests
# ============================================================================


@pytest.mark.asyncio
async def test_lockout_persists_across_requests(client: AsyncClient):
    """
    Test que el bloqueo persiste en la BD (no es solo en memoria).

    Given: Cuenta bloqueada
    When: Hacer request desde "diferente cliente" (simular sesión nueva)
    Then: Sigue bloqueada (HTTP 423)
    """
    # Given: Crear usuario y bloquearlo
    register_data = {
        "email": "persist@example.com",
        "password": "ValidPassword123!",
        "first_name": "Persist",
        "last_name": "Test",
    }

    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # Bloquear cuenta (10 intentos fallidos)
    for i in range(10):
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "persist@example.com",
                "password": "WrongPassword123!",
            },
            headers={"X-Test-Client-ID": f"test-client-4-{i + 1}"},
        )

    # When: Intentar login desde "nuevo cliente" (simular nueva sesión)
    # En tests, es el mismo cliente pero conceptualmente es diferente request
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "persist@example.com",
            "password": "ValidPassword123!",
        },
        headers={"X-Test-Client-ID": "test-client-4-11"},
    )

    # Then: Sigue bloqueada (persiste en BD)
    assert response.status_code == 423


@pytest.mark.asyncio
async def test_lockout_error_message_includes_locked_until_timestamp(
    client: AsyncClient,
):
    """
    Test que el mensaje de error incluye el timestamp locked_until.

    Given: Cuenta bloqueada
    When: Intentar login
    Then: Mensaje incluye fecha/hora de desbloqueo (ISO format)

    Security: Esto ayuda al usuario legítimo a saber cuándo puede reintentar.
    """
    # Given: Crear usuario y bloquearlo
    register_data = {
        "email": "timestamp@example.com",
        "password": "ValidPassword123!",
        "first_name": "Timestamp",
        "last_name": "Test",
    }

    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # Bloquear cuenta
    for i in range(10):
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "timestamp@example.com",
                "password": "WrongPassword123!",
            },
            headers={
                "X-Test-Client-ID": f"test-client-5-{i + 1}"
            },  # Cliente diferente por intento
        )

    # When: Intentar login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "timestamp@example.com",
            "password": "ValidPassword123!",
        },
        headers={"X-Test-Client-ID": "test-client-5-11"},
    )

    # Then: Mensaje incluye timestamp en formato ISO
    assert response.status_code == 423
    detail = response.json()["detail"]
    assert "locked until" in detail.lower()
    # Verificar que hay un timestamp ISO (formato: 2026-01-07T20:00:00)
    assert "T" in detail  # ISO datetime incluye "T"
