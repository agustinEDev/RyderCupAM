"""Tests unitarios para Correlation Middleware"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCorrelationMiddleware:
    """Tests del middleware de Correlation ID"""

    async def test_generates_correlation_id_if_not_present(self, client: AsyncClient):
        """Genera correlation_id si no viene en request"""
        response = await client.get("/api/v1/countries")

        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) == 36  # UUID format

    async def test_propagates_correlation_id_from_request(self, client: AsyncClient):
        """Propaga correlation_id del request a la response"""
        custom_correlation_id = "test-correlation-123"

        response = await client.get(
            "/api/v1/countries",
            headers={"X-Correlation-ID": custom_correlation_id}
        )

        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_correlation_id

    async def test_different_requests_have_different_correlation_ids(self, client: AsyncClient):
        """Cada request tiene correlation_id único"""
        response1 = await client.get("/api/v1/countries")
        response2 = await client.get("/api/v1/countries")

        correlation_id_1 = response1.headers["X-Correlation-ID"]
        correlation_id_2 = response2.headers["X-Correlation-ID"]

        assert correlation_id_1 != correlation_id_2
