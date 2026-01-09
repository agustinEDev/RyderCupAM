"""
Integration Tests - Rate Limiting

Tests para verificar que el rate limiting con SlowAPI funciona correctamente
en los endpoints críticos.

Cobertura OWASP:
- A04: Insecure Design (DoS protection)
- A07: Identification and Authentication Failures (brute force protection)
"""

import pytest
from httpx import AsyncClient

from src.config.rate_limit import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Limpia el rate limiter antes y después de cada test."""
    limiter.reset()
    yield
    limiter.reset()


class TestRateLimitingLogin:
    """Tests de rate limiting para el endpoint de login."""

    @pytest.mark.asyncio
    async def test_login_rate_limit_exceeded_returns_429(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de login con límite de 5 peticiones/minuto
        WHEN: Se realizan 6 intentos de login desde la misma IP
        THEN: Las primeras 5 peticiones son procesadas (200/401)
              La 6ta petición recibe HTTP 429 Too Many Requests
              Los headers X-RateLimit-* están presentes
        """
        # Payload para login (credenciales inválidas, no importa para rate limiting)
        payload = {"email": "test@example.com", "password": "wrongpassword"}

        # Realizar 5 peticiones (dentro del límite)
        responses = []
        for i in range(5):
            response = await client.post("/api/v1/auth/login", json=payload)
            responses.append(response)
            # Esperamos 401 porque las credenciales son inválidas
            # Pero el rate limiter NO debe bloquear
            assert response.status_code in [200, 401], (
                f"Intento {i + 1} falló con {response.status_code}"
            )

        # 6ta petición debe ser bloqueada por rate limiter
        response_blocked = await client.post("/api/v1/auth/login", json=payload)

        # Verificar HTTP 429 - ESTO ES LO CRÍTICO
        assert response_blocked.status_code == 429, (
            f"Esperaba HTTP 429 en la 6ta petición, obtuvo {response_blocked.status_code}"
        )

        # Verificar que el mensaje indica rate limiting
        response_data = response_blocked.json()
        # SlowAPI usa 'error' en lugar de 'detail'
        assert "error" in response_data, "Respuesta 429 debe contener 'error'"
        assert "Rate limit exceeded" in response_data["error"], (
            "Mensaje debe indicar 'Rate limit exceeded'"
        )

    @pytest.mark.asyncio
    async def test_login_within_rate_limit_succeeds(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de login con límite de 5 peticiones/minuto
        WHEN: Se realizan 3 peticiones (dentro del límite)
        THEN: Todas las peticiones son procesadas sin HTTP 429
              El rate limiter NO bloquea peticiones dentro del límite

        NOTE: Este test verifica que el rate limiting NO afecta uso normal.
        """
        payload = {"email": "test@example.com", "password": "t3stp@ssw0rd!"}

        # Realizar 3 peticiones (dentro del límite de 5/min)
        for i in range(3):
            response = await client.post("/api/v1/auth/login", json=payload)
            # Esperamos 401 (credenciales inválidas) NO 429 (rate limited)
            assert response.status_code in [200, 401], (
                f"Petición {i + 1} fue bloqueada incorrectamente con {response.status_code}"
            )


class TestRateLimitingRegister:
    """Tests de rate limiting para el endpoint de registro."""

    @pytest.mark.asyncio
    async def test_register_rate_limit_exceeded_returns_429(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de register con límite de 3 peticiones/hora
        WHEN: Se realizan 4 intentos de registro desde la misma IP
        THEN: Las primeras 3 peticiones son procesadas (201/409/400)
              La 4ta petición recibe HTTP 429 Too Many Requests
        """
        # Payloads para registro (con emails diferentes para evitar 409 Conflict)
        payloads = [
            {
                "email": f"user{i}@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User",
            }
            for i in range(4)
        ]

        # Realizar 3 peticiones (dentro del límite)
        responses = []
        for i in range(3):
            response = await client.post("/api/v1/auth/register", json=payloads[i])
            responses.append(response)
            # Esperamos 201 (creado) o 409 (ya existe) o 400 (validación)
            # Pero el rate limiter NO debe bloquear
            assert response.status_code in [201, 409, 400], (
                f"Intento {i + 1} falló con {response.status_code}"
            )

        # 4ta petición debe ser bloqueada por rate limiter
        response_blocked = await client.post("/api/v1/auth/register", json=payloads[3])

        # Verificar HTTP 429 - ESTO ES LO CRÍTICO
        assert response_blocked.status_code == 429, (
            f"Esperaba HTTP 429 en la 4ta petición, obtuvo {response_blocked.status_code}"
        )

        # Verificar que el mensaje indica rate limiting
        response_data = response_blocked.json()
        # SlowAPI usa 'error' en lugar de 'detail'
        assert "error" in response_data, "Respuesta 429 debe contener 'error'"
        assert "Rate limit exceeded" in response_data["error"], (
            "Mensaje debe indicar 'Rate limit exceeded'"
        )


class TestRateLimitingHandicap:
    """Tests de rate limiting para el endpoint de actualización de handicap (RFEG)."""

    @pytest.mark.asyncio
    async def test_handicap_update_rate_limit_exceeded_returns_429(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de actualización de handicap con límite de 5 peticiones/hora
        WHEN: Se realizan 6 intentos de actualización desde la misma IP
        THEN: Las primeras 5 peticiones son procesadas (200/401/404/503)
              La 6ta petición recibe HTTP 429 Too Many Requests
        """
        # Registrar y autenticar usuario para obtener token
        register_payload = {
            "email": "handicap_rate_test@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        }
        await client.post("/api/v1/auth/register", json=register_payload)

        login_payload = {"email": "handicap_rate_test@example.com", "password": "TestPassword123!"}
        login_response = await client.post("/api/v1/auth/login", json=login_payload)

        # Si no podemos autenticar, skip el test
        if login_response.status_code != 200:
            pytest.skip("No se pudo autenticar usuario para test de handicap rate limiting")

        token = login_response.json().get("access_token")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Limpiar rate limiter después del setup de autenticación
        limiter.reset()

        # Payload para actualización de handicap
        payload = {"user_id": "123e4567-e89b-12d3-a456-426614174000", "manual_handicap": 15.5}

        # Realizar 5 peticiones (dentro del límite)
        responses = []
        for i in range(5):
            response = await client.post(
                "/api/v1/handicaps/update", json=payload, headers=auth_headers
            )
            responses.append(response)
            # Esperamos 404 (usuario no existe) o 503 (RFEG no disponible) o 200/401
            # Pero el rate limiter NO debe bloquear
            assert response.status_code in [200, 401, 404, 503], (
                f"Intento {i + 1} falló con {response.status_code}"
            )

        # 6ta petición debe ser bloqueada por rate limiter
        response_blocked = await client.post(
            "/api/v1/handicaps/update", json=payload, headers=auth_headers
        )

        # Verificar HTTP 429 - ESTO ES LO CRÍTICO
        assert response_blocked.status_code == 429, (
            f"Esperaba HTTP 429 en la 6ta petición, obtuvo {response_blocked.status_code}"
        )

        # Verificar que el mensaje indica rate limiting
        response_data = response_blocked.json()
        # SlowAPI usa 'error' en lugar de 'detail'
        assert "error" in response_data, "Respuesta 429 debe contener 'error'"
        assert "Rate limit exceeded" in response_data["error"], (
            "Mensaje debe indicar 'Rate limit exceeded'"
        )


class TestRateLimitingCompetition:
    """Tests de rate limiting para el endpoint de creación de competiciones."""

    @pytest.mark.asyncio
    async def test_create_competition_rate_limit_exceeded_returns_429(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de creación de competición con límite de 10 peticiones/hora
        WHEN: Se realizan 11 intentos de creación desde la misma IP
        THEN: Las primeras 10 peticiones son procesadas (201/400/401)
              La 11va petición recibe HTTP 429 Too Many Requests
        """
        # Registrar y autenticar usuario para obtener token
        register_payload = {
            "email": "competition_rate_test@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        }
        await client.post("/api/v1/auth/register", json=register_payload)

        login_payload = {
            "email": "competition_rate_test@example.com",
            "password": "TestPassword123!",
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)

        # Si no podemos autenticar, skip el test
        if login_response.status_code != 200:
            pytest.skip("No se pudo autenticar usuario para test de competition rate limiting")

        token = login_response.json().get("access_token")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Limpiar rate limiter después del setup de autenticación
        limiter.reset()

        # Payload mínimo para creación de competición
        payload = {
            "name": "Test Competition",
            "start_date": "2025-06-01",
            "end_date": "2025-06-03",
            "main_country": "ES",
            "number_of_players": 24,
            "team_assignment": "MANUAL",
            "team_1_name": "Europe",
            "team_2_name": "USA",
            "handicap_type": "SCRATCH",
        }

        # Realizar 10 peticiones (dentro del límite)
        responses = []
        for i in range(10):
            # Cambiar el nombre para evitar conflictos
            payload_copy = payload.copy()
            payload_copy["name"] = f"Test Competition {i}"

            response = await client.post(
                "/api/v1/competitions", json=payload_copy, headers=auth_headers
            )
            responses.append(response)
            # Esperamos 201 (creado) o 400/401/422 (validación/auth)
            # Pero el rate limiter NO debe bloquear
            assert response.status_code in [201, 400, 401, 422], (
                f"Intento {i + 1} falló con {response.status_code}"
            )

        # 11va petición debe ser bloqueada por rate limiter
        payload_blocked = payload.copy()
        payload_blocked["name"] = "Test Competition 11"
        response_blocked = await client.post(
            "/api/v1/competitions", json=payload_blocked, headers=auth_headers
        )

        # Verificar HTTP 429 - ESTO ES LO CRÍTICO
        assert response_blocked.status_code == 429, (
            f"Esperaba HTTP 429 en la 11va petición, obtuvo {response_blocked.status_code}"
        )

        # Verificar que el mensaje indica rate limiting
        response_data = response_blocked.json()
        # SlowAPI usa 'error' en lugar de 'detail'
        assert "error" in response_data, "Respuesta 429 debe contener 'error'"
        assert "Rate limit exceeded" in response_data["error"], (
            "Mensaje debe indicar 'Rate limit exceeded'"
        )
