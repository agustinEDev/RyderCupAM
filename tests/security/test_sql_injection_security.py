"""
Security Tests - SQL Injection

Tests que intentan explotar vulnerabilidades de inyección SQL
para validar protección mediante Pydantic validation y SQLAlchemy ORM.

OWASP: A03 (Injection)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSQLInjectionLoginEndpoint:
    """Tests de SQL injection en endpoint de login."""

    async def test_sql_injection_in_email_field(self, client: AsyncClient):
        """
        Given: Un atacante intenta SQL injection en el campo email
        When: Se envía un payload malicioso (ej. ' OR '1'='1)
        Then: El intento debe ser rechazado por validación de Pydantic (422)
        """
        malicious_payloads = [
            "' OR '1'='1",
            "admin'--",
            "' OR 1=1--",
            "admin' OR '1'='1'--",
            "'; DROP TABLE users--",
        ]

        for payload in malicious_payloads:
            login_data = {"email": payload, "password": "anypassword"}
            response = await client.post("/api/v1/auth/login", json=login_data)

            # Debe fallar con validación de Pydantic (email inválido)
            assert response.status_code == 422, (
                f"Payload '{payload}' debe ser rechazado con 422 (validation error)"
            )

    async def test_sql_injection_in_password_field(self, client: AsyncClient):
        """
        Given: Un atacante intenta SQL injection en el campo password
        When: Se envía un payload SQL malicioso
        Then: El intento debe fallar sin revelar información de la BD
        """
        # Crear un usuario válido primero
        register_data = {
            "email": "victim@example.com",
            "password": "ValidPassword123!",
            "first_name": "Victim",
            "last_name": "User",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Intentar SQL injection en password
        malicious_passwords = [
            "' OR '1'='1",
            "password' OR 1=1--",
            "'; DROP TABLE users--",
        ]

        for payload in malicious_passwords:
            login_data = {"email": "victim@example.com", "password": payload}
            response = await client.post("/api/v1/auth/login", json=login_data)

            # Debe fallar con 401 (credenciales inválidas), NO con error de BD
            assert response.status_code in [401, 404], (
                "SQL injection en password debe fallar con 401/404, no con error de BD"
            )


@pytest.mark.asyncio
class TestSQLInjectionRegisterEndpoint:
    """Tests de SQL injection en endpoint de registro."""

    async def test_sql_injection_in_registration_fields(self, client: AsyncClient):
        """
        Given: Un atacante intenta SQL injection en campos de registro
        When: Se envían payloads maliciosos en first_name, last_name
        Then: Los valores deben ser sanitizados y almacenados de forma segura
        """
        malicious_name = "Robert'; DROP TABLE users--"

        register_data = {
            "email": "sqlinjection@example.com",
            "password": "ValidPassword123!",
            "first_name": malicious_name,
            "last_name": "User",
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        # El registro puede fallar con 422 (validación) o ser sanitizado
        # Si pasa validación, el payload debe ser sanitizado (sin ejecutar SQL)
        assert response.status_code in [201, 422], (
            "El registro debe fallar con validación o sanitizar el input"
        )

        if response.status_code == 201:
            # Verificar que el nombre se guardó como texto plano (sin ejecutar SQL)
            # La tabla users debe seguir existiendo (no se ejecutó DROP TABLE)
            login_data = {"email": "sqlinjection@example.com", "password": "ValidPassword123!"}
            login_response = await client.post("/api/v1/auth/login", json=login_data)
            assert login_response.status_code == 200, (
                "La tabla users debe seguir existiendo después del intento de SQL injection"
            )


@pytest.mark.asyncio
class TestSQLInjectionCompetitionEndpoint:
    """Tests de SQL injection en endpoints de competiciones."""

    async def test_sql_injection_in_competition_name(self, authenticated_client):
        """
        Given: Un atacante autenticado intenta SQL injection en nombre de competición
        When: Se crea una competición con nombre malicioso
        Then: El nombre debe ser sanitizado y almacenado de forma segura
        """
        client, _user_data = authenticated_client

        malicious_name = "Competition'; DROP TABLE competitions--"

        competition_data = {
            "name": malicious_name,
            "start_date": "2025-12-25",
            "end_date": "2025-12-26",
            "main_country": "ES",
            "handicap_type": "PERCENTAGE",
            "handicap_percentage": 95,
            "max_players": 100,
            "team_assignment": "MANUAL",
        }

        response = await client.post("/api/v1/competitions", json=competition_data)

        # El nombre puede ser sanitizado o rechazado por validación
        assert response.status_code in [201, 400, 422], (
            "El input debe ser sanitizado o rechazado por validación"
        )

        if response.status_code == 201:
            # Verificar que la tabla competitions sigue existiendo
            list_response = await client.get("/api/v1/competitions")
            assert list_response.status_code == 200, "La tabla competitions debe seguir existiendo"


@pytest.mark.asyncio
class TestORMProtection:
    """Tests que verifican que SQLAlchemy ORM protege contra SQL injection."""

    async def test_orm_parameterized_queries(self, client: AsyncClient):
        """
        Given: SQLAlchemy ORM usa consultas parametrizadas
        When: Se realizan operaciones normales de BD
        Then: No debe ser posible ejecutar SQL arbitrario
        """
        # Este test documenta que SQLAlchemy protege automáticamente
        # contra SQL injection mediante consultas parametrizadas

        # Intentar crear usuario con caracteres especiales SQL
        register_data = {
            "email": "test';--@example.com",  # Email inválido
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        # Debe fallar por validación de email, no por error de SQL
        assert response.status_code == 422, (
            "Debe fallar con validación de Pydantic, no con error de SQL"
        )

    async def test_no_raw_sql_execution(self, client: AsyncClient):
        """
        Given: El sistema NO usa consultas SQL raw (solo ORM)
        When: Se intenta inyectar SQL en diferentes endpoints
        Then: Ningún SQL arbitrario debe ejecutarse

        NOTE: Este test documenta la arquitectura del sistema.
        El uso de SQLAlchemy ORM (en lugar de SQL raw) previene SQL injection.
        """
        # Lista de payloads comunes de SQL injection
        sql_payloads = [
            "1' OR '1'='1",
            "'; DROP TABLE users--",
            "admin'--",
            "1' UNION SELECT NULL--",
        ]

        # Intentar en diferentes campos
        for payload in sql_payloads:
            # Intento 1: Login
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"{payload}@example.com",  # Will fail email validation
                    "password": payload,
                },
            )
            # Debe fallar con 422 (validación) o 401 (credenciales), nunca error SQL
            assert response.status_code in [401, 404, 422], (
                f"Payload '{payload}' no debe causar error de SQL"
            )
