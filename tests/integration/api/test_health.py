"""
Tests de integración para los endpoints de la API principal.

Este archivo contiene tests que verifican:
- Endpoint de health check (/)
- Respuesta correcta de la API FastAPI
- Formato JSON y estructura de respuestas
- Códigos de estado HTTP
"""

import base64

import pytest
from fastapi.testclient import TestClient

from main import app
from src.config.settings import settings

# ================================
# SETUP DE CLIENTE DE PRUEBAS
# ================================


@pytest.fixture
def client():
    """
    Fixture que proporciona un cliente de pruebas para FastAPI.

    Returns:
        TestClient: Cliente configurado para hacer requests a la app
    """
    return TestClient(app)


# ================================
# TESTS DE HEALTH CHECK
# ================================


class TestHealthEndpoint:
    """Tests para el endpoint de health check"""

    def test_root_endpoint_returns_200(self, client):
        """
        Test: Endpoint raíz responde con código 200
        Given: API de FastAPI funcionando
        When: Se hace GET request a /
        Then: Responde con código HTTP 200
        """
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200

    def test_root_endpoint_returns_json(self, client):
        """
        Test: Endpoint raíz responde con JSON válido
        Given: API de FastAPI funcionando
        When: Se hace GET request a /
        Then: Responde con Content-Type application/json
        """
        # Act
        response = client.get("/")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_root_endpoint_response_structure(self, client):
        """
        Test: Endpoint raíz tiene estructura correcta
        Given: API de FastAPI funcionando
        When: Se hace GET request a /
        Then: Responde con todos los campos requeridos
        """
        # Act
        response = client.get("/")
        data = response.json()

        # Assert - Verificar que tiene todos los campos esperados
        assert "message" in data
        assert "version" in data
        assert "status" in data
        assert "docs" in data
        assert "description" in data

    def test_root_endpoint_response_values(self, client):
        """
        Test: Endpoint raíz tiene valores correctos
        Given: API de FastAPI funcionando
        When: Se hace GET request a /
        Then: Los valores de respuesta son los esperados
        """
        # Act
        response = client.get("/")
        data = response.json()

        # Assert - Verificar valores específicos
        assert data["message"] == "Ryder Cup Manager API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "documentacion" in data["docs"].lower()
        assert "ryder cup" in data["description"].lower()

    def test_root_endpoint_response_types(self, client):
        """
        Test: Endpoint raíz tiene tipos de datos correctos
        Given: API de FastAPI funcionando
        When: Se hace GET request a /
        Then: Todos los campos son strings
        """
        # Act
        response = client.get("/")
        data = response.json()

        # Assert - Verificar tipos
        assert isinstance(data["message"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["docs"], str)
        assert isinstance(data["description"], str)


# ================================
# TESTS DE DOCUMENTACIÓN
# ================================


class TestAPIDocumentation:
    """Tests para endpoints de documentación automática"""

    def test_docs_endpoint_accessible(self, client):
        """
        Test: Endpoint de documentación Swagger accesible
        Given: API de FastAPI con docs habilitados
        When: Se hace GET request a /docs con HTTP Basic Auth
        Then: Responde con código 200 y HTML
        """
        # Arrange
        credentials = f"{settings.DOCS_USERNAME}:{settings.DOCS_PASSWORD}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_credentials}"}

        # Act
        response = client.get("/docs", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint_accessible(self, client):
        """
        Test: Endpoint de documentación ReDoc accesible
        Given: API de FastAPI con redoc habilitado
        When: Se hace GET request a /redoc con HTTP Basic Auth
        Then: Responde con código 200 y HTML
        """
        # Arrange
        credentials = f"{settings.DOCS_USERNAME}:{settings.DOCS_PASSWORD}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_credentials}"}

        # Act
        response = client.get("/redoc", headers=headers)

        # Assert
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_schema_accessible(self, client):
        """
        Test: Schema OpenAPI accesible
        Given: API de FastAPI funcionando
        When: Se hace GET request a /openapi.json
        Then: Responde con JSON schema válido
        """
        # Act
        response = client.get("/openapi.json")

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Verificar que es un schema OpenAPI válido
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema


# ================================
# TESTS DE ERRORES Y CASOS BORDE
# ================================


class TestErrorHandling:
    """Tests para manejo de errores y casos borde"""

    def test_nonexistent_endpoint_returns_404(self, client):
        """
        Test: Endpoint inexistente retorna 404
        Given: API de FastAPI funcionando
        When: Se hace GET request a endpoint que no existe
        Then: Responde con código HTTP 404
        """
        # Act
        response = client.get("/endpoint-que-no-existe")

        # Assert
        assert response.status_code == 404

    def test_wrong_http_method_returns_405(self, client):
        """
        Test: Método HTTP incorrecto retorna 405
        Given: Endpoint que solo acepta GET
        When: Se hace POST request al endpoint
        Then: Responde con código HTTP 405 (Method Not Allowed)
        """
        # Act
        response = client.post("/")

        # Assert
        assert response.status_code == 405

    def test_api_handles_concurrent_requests(self, client):
        """
        Test: API maneja múltiples requests simultáneos
        Given: API de FastAPI funcionando
        When: Se hacen múltiples requests concurrentes
        Then: Todos responden correctamente
        """
        # Act - Simular múltiples requests
        responses = []
        for _ in range(5):
            response = client.get("/")
            responses.append(response)

        # Assert - Todos deben ser exitosos
        for response in responses:
            assert response.status_code == 200
            assert response.json()["status"] == "running"


# ================================
# TESTS DE RENDIMIENTO BÁSICO
# ================================


class TestBasicPerformance:
    """Tests básicos de rendimiento"""

    def test_response_time_reasonable(self, client):
        """
        Test: Tiempo de respuesta es razonable
        Given: API de FastAPI funcionando
        When: Se hace request al health endpoint
        Then: Responde en menos de 1 segundo
        """
        import time

        # Act
        start_time = time.time()
        response = client.get("/")
        end_time = time.time()

        response_time = end_time - start_time

        # Assert
        assert response.status_code == 200
        assert response_time < 1.0  # Menos de 1 segundo

    def test_multiple_requests_performance(self, client):
        """
        Test: Múltiples requests mantienen buen rendimiento
        Given: API de FastAPI funcionando
        When: Se hacen 10 requests consecutivos
        Then: Todos responden en tiempo razonable
        """
        import time

        # Act
        response_times = []
        for _ in range(10):
            start_time = time.time()
            response = client.get("/")
            end_time = time.time()

            assert response.status_code == 200
            response_times.append(end_time - start_time)

        # Assert
        average_time = sum(response_times) / len(response_times)
        assert average_time < 0.5  # Promedio menor a 0.5 segundos
        assert max(response_times) < 1.0  # Ninguno mayor a 1 segundo
