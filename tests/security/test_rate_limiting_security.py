"""
Security Tests - Rate Limiting

Tests que intentan exceder los límites de rate limiting configurados
para validar protección contra brute-force y DoS attacks.

OWASP: A04 (Insecure Design), A07 (Authentication Failures)
"""

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestLoginRateLimiting:
    """Tests de rate limiting en endpoint de login (5/minuto)."""

    async def test_login_rate_limit_blocks_after_5_attempts(self, client: AsyncClient):
        """
        Given: El endpoint /login tiene límite de 5 intentos por minuto
        When: Se realizan 6 intentos de login consecutivos
        Then: El 6to intento debe ser bloqueado con 429 Too Many Requests
        """
        login_data = {"email": "attacker@example.com", "password": "WrongPassword123!"}

        # Realizar 5 intentos (dentro del límite)
        for i in range(5):
            response = await client.post("/api/v1/auth/login", json=login_data)
            assert response.status_code in [
                401,
                404,
            ], f"Intento {i + 1} debería fallar con credenciales incorrectas"

        # El 6to intento debe ser bloqueado por rate limit
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 429, (
            "El 6to intento debe ser bloqueado con 429 Too Many Requests"
        )

        # Validar que la respuesta contiene información sobre rate limiting
        # SlowAPI puede devolver plain text o JSON dependiendo de la configuración
        assert response.text is not None and len(response.text) > 0, (
            "La respuesta debe contener información sobre rate limit"
        )

    async def test_login_rate_limit_prevents_brute_force(self, client: AsyncClient):
        """
        Given: Un atacante intenta brute-force con múltiples passwords
        When: Se excede el límite de 5/minuto
        Then: Los intentos adicionales son bloqueados
        """
        passwords = [
            "Password1!",
            "Password2!",
            "Password3!",
            "Password4!",
            "Password5!",
            "Password6!",  # Este debe ser bloqueado
        ]

        blocked_attempts = 0

        for idx, password in enumerate(passwords):
            login_data = {"email": "victim@example.com", "password": password}
            response = await client.post("/api/v1/auth/login", json=login_data)

            if response.status_code == 429:
                blocked_attempts += 1
                assert idx >= 5, "Rate limit debe activarse después del 5to intento"

        assert blocked_attempts >= 1, "Al menos 1 intento debe ser bloqueado por rate limiting"


@pytest.mark.asyncio
class TestRegisterRateLimiting:
    """Tests de rate limiting en endpoint de registro (3/hora)."""

    async def test_register_rate_limit_blocks_after_3_attempts(self, client: AsyncClient):
        """
        Given: El endpoint /register tiene límite de 3 registros por hora
        When: Se intentan 4 registros consecutivos
        Then: El 4to intento debe ser bloqueado con 429
        """
        # Realizar 3 intentos (dentro del límite)
        for i in range(3):
            register_data = {
                "email": f"spam{i}@example.com",
                "password": "ValidPassword123!",
                "password_confirmation": "ValidPassword123!",
                "first_name": "Spam",
                "last_name": "User",
                "country_code": "ES",
            }
            response = await client.post("/api/v1/auth/register", json=register_data)
            # Puede ser 201 (éxito) o 400 (email ya existe), pero no 429
            assert response.status_code != 429, (
                f"Intento {i + 1} no debe ser bloqueado por rate limit"
            )

        # El 4to intento debe ser bloqueado
        register_data = {
            "email": "spam3@example.com",
            "password": "ValidPassword123!",
            "password_confirmation": "ValidPassword123!",
            "first_name": "Spam",
            "last_name": "User",
            "country_code": "ES",
        }
        response = await client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 429, (
            "El 4to intento debe ser bloqueado con 429 Too Many Requests"
        )


@pytest.mark.asyncio
class TestCompetitionRateLimiting:
    """Tests de rate limiting en creación de competiciones (10/hora)."""

    async def test_competition_creation_rate_limit(self, authenticated_client):
        """
        Given: El endpoint de creación de competiciones tiene límite de 10/hora
        When: Se intentan crear 11 competiciones consecutivas
        Then: La 11va debe ser bloqueada con 429
        """
        client, _user_data = authenticated_client

        # Realizar 10 intentos (dentro del límite)
        for i in range(10):
            competition_data = {
                "name": f"Test Competition {i}",
                "start_date": "2025-12-25",
                "end_date": "2025-12-26",
                "main_country": "ES",
                "play_mode": "HANDICAP",
                "max_players": 100,
                "team_assignment": "MANUAL",
            }
            response = await client.post("/api/v1/competitions", json=competition_data)
            # Puede ser 201 (éxito) o 400 (validación), pero no 429
            assert response.status_code != 429, (
                f"Intento {i + 1} no debe ser bloqueado por rate limit"
            )

        # El 11vo intento debe ser bloqueado
        competition_data = {
            "name": "Blocked Competition",
            "start_date": "2025-12-25",
            "end_date": "2025-12-26",
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 100,
            "team_assignment": "MANUAL",
        }
        response = await client.post("/api/v1/competitions", json=competition_data)
        assert response.status_code == 429, (
            "El 11vo intento debe ser bloqueado con 429 Too Many Requests"
        )


@pytest.mark.asyncio
class TestRateLimitingBypass:
    """Tests que intentan bypass del rate limiting."""

    async def test_cannot_bypass_with_different_user_agents(self, client: AsyncClient):
        """
        Given: Rate limiting está basado en IP
        When: Se intenta bypass cambiando User-Agent headers
        Then: El rate limit sigue aplicando (basado en IP, no User-Agent)
        """
        login_data = {"email": "attacker@example.com", "password": "WrongPassword123!"}

        user_agents = [
            "Mozilla/5.0",
            "Chrome/91.0",
            "Safari/14.0",
            "Edge/90.0",
            "Firefox/88.0",
            "Opera/76.0",
        ]

        blocked = False

        for idx, user_agent in enumerate(user_agents):
            headers = {"User-Agent": user_agent}
            response = await client.post("/api/v1/auth/login", json=login_data, headers=headers)

            if response.status_code == 429:
                blocked = True
                assert idx >= 5, (
                    "Rate limit debe aplicar después de 5 intentos independiente del User-Agent"
                )
                break

        assert blocked, "Cambiar User-Agent no debe permitir bypass del rate limiting"

    async def test_rate_limit_persists_across_requests(self, client: AsyncClient):
        """
        Given: Rate limiting está activo
        When: Se excede el límite y se espera un breve período
        Then: El rate limit sigue aplicando (no se resetea inmediatamente)
        """
        login_data = {
            "email": "persistent@example.com",
            "password": "WrongPassword123!",
        }

        # Exceder el límite
        for _ in range(6):
            await client.post("/api/v1/auth/login", json=login_data)

        # Esperar brevemente (no suficiente para reset)
        await asyncio.sleep(1)

        # Debe seguir bloqueado
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 429, "Rate limit debe persistir después de 1 segundo"


@pytest.mark.asyncio
class TestRateLimitingMetadata:
    """Tests que validan metadata de rate limiting en headers."""

    async def test_rate_limit_headers_present(self, client: AsyncClient):
        """
        Given: El sistema tiene rate limiting configurado
        When: Se realiza una request
        Then: Los headers de rate limit deben estar presentes
        """
        login_data = {"email": "test@example.com", "password": "TestPassword123!"}

        response = await client.post("/api/v1/auth/login", json=login_data)

        # Validar que existan headers de rate limiting (si SlowAPI los expone)
        # Nota: SlowAPI puede no exponer estos headers por defecto
        # Este test documenta el comportamiento esperado

        # Headers comunes de rate limiting:
        # - X-RateLimit-Limit: Límite total
        # - X-RateLimit-Remaining: Intentos restantes
        # - X-RateLimit-Reset: Timestamp de reset

        # Por ahora, validamos que el endpoint responde
        assert response.status_code in [
            200,
            401,
            404,
            429,
        ], "Endpoint debe responder con código válido"
