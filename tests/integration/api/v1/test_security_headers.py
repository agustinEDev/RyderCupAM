"""
Integration Tests - Security Headers

Tests para verificar que los Security Headers HTTP están presentes
en todas las respuestas de la API.

Cobertura OWASP:
- A02: Cryptographic Failures (HSTS)
- A03: Injection (X-XSS-Protection)
- A04: Insecure Design (X-Frame-Options)
- A05: Security Misconfiguration (todos los headers)
- A07: Authentication Failures (X-Frame-Options, Cache-Control)
"""

import pytest
from httpx import AsyncClient


class TestSecurityHeaders:
    """Tests de Security Headers HTTP en endpoints públicos y protegidos."""

    @pytest.mark.asyncio
    async def test_root_endpoint_has_security_headers(self, client: AsyncClient):
        """
        GIVEN: Un endpoint público (root /)
        WHEN: Se realiza una petición GET
        THEN: La respuesta incluye todos los security headers configurados
        """
        response = await client.get("/")

        # Verificar que la petición fue exitosa
        assert response.status_code == 200

        # Verificar presencia de cada security header
        headers = response.headers

        # 1. Strict-Transport-Security (HSTS)
        assert "strict-transport-security" in headers, (
            "Falta header HSTS - Vulnerable a MITM downgrade attacks"
        )
        assert "max-age" in headers["strict-transport-security"].lower(), (
            "HSTS debe incluir max-age"
        )
        assert "includesubdomains" in headers["strict-transport-security"].lower(), (
            "HSTS debe incluir includeSubdomains para proteger subdominios"
        )

        # 2. X-Frame-Options
        assert "x-frame-options" in headers, (
            "Falta header X-Frame-Options - Vulnerable a clickjacking"
        )
        assert headers["x-frame-options"].upper() in ["DENY", "SAMEORIGIN"], (
            "X-Frame-Options debe ser DENY o SAMEORIGIN"
        )

        # 3. X-Content-Type-Options
        assert "x-content-type-options" in headers, (
            "Falta header X-Content-Type-Options - Vulnerable a MIME-sniffing XSS"
        )
        assert headers["x-content-type-options"].lower() == "nosniff", (
            "X-Content-Type-Options debe ser 'nosniff'"
        )

        # 4. Referrer-Policy
        assert "referrer-policy" in headers, (
            "Falta header Referrer-Policy - Puede filtrar información sensible"
        )

        # 5. Cache-Control
        assert "cache-control" in headers, (
            "Falta header Cache-Control - Puede cachear datos sensibles"
        )

        # 6. X-XSS-Protection (opcional, obsoleto pero presente en configuración)
        # Nota: Valor '0' es correcto (desactivado) ya que puede causar vulnerabilidades
        if "x-xss-protection" in headers:
            assert headers["x-xss-protection"] == "0", (
                "X-XSS-Protection debe ser '0' (desactivado) en navegadores modernos"
            )

    @pytest.mark.asyncio
    async def test_login_endpoint_has_security_headers(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de autenticación (login)
        WHEN: Se realiza una petición POST (incluso con credenciales inválidas)
        THEN: La respuesta incluye security headers (especialmente X-Frame-Options y Cache-Control)

        IMPORTANTE: X-Frame-Options previene clickjacking en formularios de login
                    Cache-Control previene cacheo de tokens de autenticación
        """
        # Intentar login con credenciales inválidas (no importa para este test)
        payload = {"email": "test@example.com", "password": "wrongpassword"}
        response = await client.post("/api/v1/auth/login", json=payload)

        # La petición puede fallar (401), pero debe tener security headers
        assert response.status_code in [200, 401, 422]

        headers = response.headers

        # X-Frame-Options es CRÍTICO en endpoints de login (previene clickjacking)
        assert "x-frame-options" in headers, (
            "Login DEBE tener X-Frame-Options para prevenir clickjacking"
        )

        # Cache-Control es CRÍTICO en endpoints de auth (previene cacheo de tokens)
        assert "cache-control" in headers, (
            "Login DEBE tener Cache-Control para prevenir cacheo de tokens"
        )
        assert "no-store" in headers["cache-control"].lower(), (
            "Cache-Control debe incluir 'no-store' para prevenir cacheo"
        )

        # Verificar también HSTS y X-Content-Type-Options
        assert "strict-transport-security" in headers
        assert "x-content-type-options" in headers

    @pytest.mark.asyncio
    async def test_register_endpoint_has_security_headers(self, client: AsyncClient):
        """
        GIVEN: Un endpoint de registro de usuarios
        WHEN: Se realiza una petición POST (incluso inválida)
        THEN: La respuesta incluye security headers
        """
        payload = {
            "email": "newuser@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
        }
        response = await client.post("/api/v1/auth/register", json=payload)

        # La petición puede tener diferentes resultados, pero debe tener headers
        assert response.status_code in [201, 409, 422, 429]  # 429 por rate limiting

        headers = response.headers

        # Verificar headers críticos
        assert "x-frame-options" in headers
        assert "x-content-type-options" in headers
        assert "cache-control" in headers

    @pytest.mark.asyncio
    async def test_protected_endpoint_has_security_headers(self, client: AsyncClient):
        """
        GIVEN: Un endpoint protegido que requiere autenticación
        WHEN: Se intenta acceder sin token (401 Unauthorized o 404 Not Found)
        THEN: La respuesta incluye security headers incluso en errores

        IMPORTANTE: Los security headers deben estar presentes en TODAS las respuestas,
                    incluyendo errores 401, 403, 404, 500, etc.
        """
        # Intentar acceder a endpoint protegido sin token
        response = await client.get("/api/v1/users/me")

        # Puede ser 401 (sin auth) o 404 (endpoint no existe), ambos son válidos
        assert response.status_code in [401, 404]

        headers = response.headers

        # Incluso en respuestas de error, los security headers deben estar presentes
        assert "x-frame-options" in headers, (
            "Security headers deben estar en respuestas de error también"
        )
        assert "x-content-type-options" in headers
        assert "strict-transport-security" in headers

    @pytest.mark.asyncio
    async def test_security_headers_in_competition_endpoints(self, client: AsyncClient):
        """
        GIVEN: Endpoints del módulo Competition
        WHEN: Se realiza una petición (listar competiciones)
        THEN: La respuesta incluye security headers

        Verifica que el middleware de security headers se aplica a TODOS los módulos,
        no solo al módulo User.
        """
        response = await client.get("/api/v1/competitions")

        # La petición puede requerir auth (401), retornar lista (200), o forbidden (403)
        assert response.status_code in [200, 401, 403]

        headers = response.headers

        # Verificar headers presentes
        assert "x-frame-options" in headers
        assert "x-content-type-options" in headers
        assert "strict-transport-security" in headers
        assert "referrer-policy" in headers

    @pytest.mark.asyncio
    async def test_security_headers_consistency_across_endpoints(self, client: AsyncClient):
        """
        GIVEN: Múltiples endpoints diferentes
        WHEN: Se realizan peticiones a cada uno
        THEN: Todos tienen los mismos security headers configurados

        IMPORTANTE: Consistencia es clave - todos los endpoints deben tener
                    la misma protección, sin excepciones.
        """
        endpoints_to_test = [
            "/",  # Root
            "/api/v1/auth/login",  # Auth (POST, pero usaremos GET para simplificar)
            "/api/v1/competitions",  # Competition
            "/api/v1/countries",  # Countries
        ]

        # Headers que DEBEN estar en todos los endpoints
        required_headers = {
            "strict-transport-security",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "cache-control",
        }

        for endpoint in endpoints_to_test:
            response = await client.get(endpoint)

            # No importa el status code (puede ser 200, 401, 405 Method Not Allowed, etc.)
            headers = response.headers
            headers_lower = {k.lower() for k in headers}

            # Verificar que todos los required_headers están presentes
            missing_headers = required_headers - headers_lower
            assert not missing_headers, (
                f"Endpoint {endpoint} está missing headers: {missing_headers}"
            )

    @pytest.mark.asyncio
    async def test_hsts_max_age_is_sufficient(self, client: AsyncClient):
        """
        GIVEN: El header Strict-Transport-Security (HSTS)
        WHEN: Se verifica su configuración
        THEN: El max-age debe ser >= 1 año (31536000 segundos)

        OWASP recomienda HSTS con max-age de al menos 1 año para protección efectiva.
        """
        response = await client.get("/")

        hsts_header = response.headers.get("strict-transport-security", "")

        # Extraer el valor de max-age
        import re

        match = re.search(r"max-age=(\d+)", hsts_header)
        assert match, "HSTS debe incluir max-age=<segundos>"

        max_age_seconds = int(match.group(1))

        # Verificar que sea >= 1 año (31536000 segundos)
        ONE_YEAR_SECONDS = 31536000
        assert max_age_seconds >= ONE_YEAR_SECONDS, (
            f"HSTS max-age ({max_age_seconds}s) debe ser >= 1 año ({ONE_YEAR_SECONDS}s)"
        )
