"""
Tests de Integración - CORS Configuration (v1.8.0)

Verifica que la configuración CORS funcione correctamente:
- Whitelist de orígenes permitidos
- Rechaza orígenes no autorizados
- Headers CORS correctos en respuestas
- allow_credentials=True para cookies httpOnly
- Preflight requests (OPTIONS) funcionan
"""

import os
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCORSConfiguration:
    """Tests de configuración CORS."""

    async def test_cors_allows_configured_origin(
        self,
        client: AsyncClient,
    ):
        """
        Test: Origen configurado en allowed_origins es aceptado

        Given: Un cliente con origen en la whitelist (localhost:5173)
        When: Hace request GET /
        Then: Response incluye Access-Control-Allow-Origin con el origen
        """
        # Arrange
        headers = {"Origin": "http://localhost:5173"}

        # Act
        response = await client.get("/", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    async def test_cors_allows_multiple_configured_origins(
        self,
        client: AsyncClient,
    ):
        """
        Test: Múltiples orígenes configurados son aceptados

        Given: Varios orígenes en la whitelist
        When: Hace requests desde diferentes orígenes
        Then: Todos son aceptados con el header correcto
        """
        # Arrange
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
        ]

        # Act & Assert
        for origin in allowed_origins:
            headers = {"Origin": origin}
            response = await client.get("/", headers=headers)

            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert response.headers["access-control-allow-origin"] == origin

    async def test_cors_rejects_unauthorized_origin(
        self,
        client: AsyncClient,
    ):
        """
        Test: Origen NO configurado es rechazado

        Given: Un cliente con origen NO en la whitelist
        When: Hace request GET /
        Then: Response NO incluye Access-Control-Allow-Origin
        """
        # Arrange
        headers = {"Origin": "http://malicious-site.com"}

        # Act
        response = await client.get("/", headers=headers)

        # Assert
        assert response.status_code == 200  # El endpoint responde
        # Pero el navegador bloqueará la respuesta por falta de header CORS
        assert "access-control-allow-origin" not in response.headers

    async def test_cors_preflight_request_options(
        self,
        client: AsyncClient,
    ):
        """
        Test: Preflight request (OPTIONS) funciona correctamente

        Given: Un cliente hace OPTIONS request (preflight CORS)
        When: Solicita hacer POST con Authorization header
        Then: Response incluye headers CORS correctos
        """
        # Arrange
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }

        # Act
        response = await client.options("/api/v1/auth/login", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-methods" in response.headers
        assert "POST" in response.headers["access-control-allow-methods"]
        assert "access-control-allow-headers" in response.headers

    async def test_cors_allows_credentials_true(
        self,
        client: AsyncClient,
    ):
        """
        Test: allow_credentials=True está configurado

        Given: Un cliente hace request desde origen permitido
        When: Hace GET /
        Then: Response incluye Access-Control-Allow-Credentials: true
        """
        # Arrange
        headers = {"Origin": "http://localhost:5173"}

        # Act
        response = await client.get("/", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"

    async def test_cors_max_age_configured(
        self,
        client: AsyncClient,
    ):
        """
        Test: max_age está configurado para preflight cache

        Given: Un cliente hace OPTIONS request (preflight)
        When: Solicita POST
        Then: Response incluye Access-Control-Max-Age (1 hora)
        """
        # Arrange
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        }

        # Act
        response = await client.options("/api/v1/auth/login", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "access-control-max-age" in response.headers
        assert response.headers["access-control-max-age"] == "3600"  # 1 hora

    async def test_cors_allows_all_http_methods(
        self,
        client: AsyncClient,
    ):
        """
        Test: Todos los métodos HTTP están permitidos

        Given: Un cliente hace OPTIONS request
        When: Solicita diferentes métodos HTTP
        Then: Todos están permitidos (GET, POST, PUT, PATCH, DELETE, OPTIONS)
        """
        # Arrange
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
        }

        # Act
        response = await client.options("/api/v1/users/me", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "access-control-allow-methods" in response.headers
        allowed_methods = response.headers["access-control-allow-methods"]
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]:
            assert method in allowed_methods

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "FRONTEND_ORIGINS": ""})
    async def test_cors_fails_in_production_without_frontend_origins(self):
        """
        Test: En producción sin FRONTEND_ORIGINS lanza error

        Given: ENVIRONMENT=production y FRONTEND_ORIGINS vacío
        When: Se intenta importar get_cors_config()
        Then: Lanza ValueError con mensaje claro
        """
        # Arrange & Act & Assert
        from src.config.cors_config import get_cors_config

        with pytest.raises(ValueError) as exc_info:
            get_cors_config()

        assert "FRONTEND_ORIGINS no está configurado en producción" in str(exc_info.value)

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "FRONTEND_ORIGINS": "*"})
    async def test_cors_rejects_wildcard_in_production(self):
        """
        Test: Wildcard (*) es rechazado en producción

        Given: ENVIRONMENT=production y FRONTEND_ORIGINS='*'
        When: Se intenta importar get_cors_config()
        Then: Lanza ValueError rechazando wildcard
        """
        # Arrange & Act & Assert
        from src.config.cors_config import get_cors_config

        with pytest.raises(ValueError) as exc_info:
            get_cors_config()

        assert "No se permite el wildcard '*' en producción" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "FRONTEND_ORIGINS": "https://app.rydercupfriends.com,https://www.rydercupfriends.com",
        },
    )
    async def test_cors_uses_only_frontend_origins_in_production(self):
        """
        Test: En producción solo usa FRONTEND_ORIGINS (no localhost)

        Given: ENVIRONMENT=production y FRONTEND_ORIGINS configurado
        When: Se obtiene la configuración CORS
        Then: Solo incluye los orígenes de FRONTEND_ORIGINS
        """
        # Arrange & Act
        # Necesitamos reimportar el módulo para que lea las nuevas variables
        import importlib

        import src.config.cors_config
        from src.config.cors_config import get_allowed_origins
        importlib.reload(src.config.cors_config)

        allowed_origins = get_allowed_origins()

        # Assert - Verificación exacta de URLs (no substring matching por seguridad)
        assert len(allowed_origins) == 2
        assert allowed_origins == [
            "https://app.rydercupfriends.com",
            "https://www.rydercupfriends.com"
        ]
        # Verificar que NO incluye orígenes de desarrollo
        assert not any(origin.startswith("http://localhost") for origin in allowed_origins)

    async def test_cors_headers_present_in_authenticated_endpoints(
        self,
        authenticated_client: tuple,
    ):
        """
        Test: Endpoints autenticados también tienen headers CORS

        Given: Un usuario autenticado hace request desde origen permitido
        When: Hace GET /api/v1/users/profile
        Then: Response incluye headers CORS correctos
        """
        # Arrange
        client, _user_data = authenticated_client
        headers = {
            "Origin": "http://localhost:5173",
        }

        # Act
        response = await client.get("/api/v1/auth/current-user", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"
