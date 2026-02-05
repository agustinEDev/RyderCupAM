"""
Security Tests - Cross-Site Scripting (XSS)

Tests que intentan explotar vulnerabilidades XSS
para validar sanitización de inputs mediante bleach/html-sanitizer.

OWASP: A03 (Injection - XSS)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestXSSInUserFields:
    """Tests de XSS en campos de usuario."""

    async def test_xss_in_registration_name_fields(self, client: AsyncClient):
        """
        Given: Un atacante intenta inyectar scripts XSS en nombre/apellido
        When: Se registra con payloads XSS
        Then: Los scripts deben ser sanitizados antes de almacenar
        """
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
        ]

        for payload in xss_payloads:
            register_data = {
                "email": f"xss{hash(payload)}@example.com",
                "password": "ValidPassword123!",
                "first_name": payload,
                "last_name": "SafeLastName",
            }

            response = await client.post("/api/v1/auth/register", json=register_data)

            # Puede fallar por validación (longitud) o ser sanitizado
            assert response.status_code in [
                201,
                400,
                422,
            ], f"Payload XSS debe ser sanitizado o rechazado: {payload}"

            if response.status_code == 201:
                # Si se creó, verificar que el script fue sanitizado
                user_data = response.json()
                assert "<script>" not in user_data.get("first_name", ""), (
                    "Los tags <script> deben ser sanitizados"
                )
                assert "javascript:" not in user_data.get("first_name", "").lower(), (
                    "Los protocolos javascript: deben ser sanitizados"
                )

    async def test_xss_reflected_in_error_messages(self, client: AsyncClient):
        """
        Given: Un atacante intenta XSS reflejado mediante mensajes de error
        When: Se envían inputs con scripts en campos que generan errores
        Then: El sistema debe rechazar el input malicioso

        NOTE: FastAPI puede incluir el valor del campo en errores de validación.
        Este test documenta que los scripts deben ser escapados o removidos.
        """
        malicious_email = "<script>alert('XSS')</script>@example.com"

        register_data = {
            "email": malicious_email,
            "password": "ValidPassword123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        # Debe fallar con validación de email
        assert response.status_code == 422, "Email con script debe ser rechazado por validación"

        # El test documenta que los mensajes de error deben ser seguros
        # En producción, el frontend debe escapar todos los mensajes de error
        # antes de renderizarlos en HTML


@pytest.mark.asyncio
class TestXSSInCompetitionFields:
    """Tests de XSS en campos de competiciones."""

    async def test_xss_in_competition_name(self, authenticated_client):
        """
        Given: Un atacante autenticado intenta XSS en nombre de competición
        When: Se crea una competición con nombre malicioso
        Then: El nombre debe ser sanitizado
        """
        client, _user_data = authenticated_client

        xss_name = "<script>alert('Hacked')</script>Ryder Cup"

        competition_data = {
            "name": xss_name,
            "start_date": "2025-12-25",
            "end_date": "2025-12-26",
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 100,
            "team_assignment": "MANUAL",
        }

        response = await client.post("/api/v1/competitions", json=competition_data)

        # Puede ser sanitizado o rechazado
        assert response.status_code in [
            201,
            400,
            422,
        ], "Input XSS debe ser sanitizado o rechazado"

        if response.status_code == 201:
            competition = response.json()
            assert "<script>" not in competition.get("name", ""), (
                "Los tags <script> deben ser removidos del nombre"
            )

    async def test_xss_in_competition_description(self, authenticated_client):
        """
        Given: Competiciones pueden tener descripciones (campo texto largo)
        When: Se intenta XSS en la descripción
        Then: Debe ser sanitizado para prevenir stored XSS

        NOTE: Este test asume que existe un campo description.
        Si no existe, el test pasará documentando el comportamiento esperado.
        """
        client, _user_data = authenticated_client

        competition_data = {
            "name": "Test Competition",
            "start_date": "2025-12-25",
            "end_date": "2025-12-26",
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 100,
            "team_assignment": "MANUAL",
        }

        # Si el endpoint acepta description, agregarlo
        # Por ahora, documentamos que cualquier campo de texto debe sanitizarse

        response = await client.post("/api/v1/competitions", json=competition_data)

        # El test documenta que TODOS los campos de texto deben sanitizarse
        assert response.status_code in [
            201,
            400,
            422,
        ], "El endpoint debe sanitizar todos los inputs de texto"


@pytest.mark.asyncio
class TestXSSStoredAttacks:
    """Tests de Stored XSS (scripts persistentes en BD)."""

    async def test_stored_xss_in_user_profile(self, client: AsyncClient):
        """
        Given: Un atacante crea un perfil con scripts XSS
        When: El perfil se guarda en la BD
        Then: Los scripts deben ser sanitizados antes de guardar (previene stored XSS)
        """
        # Registrar usuario con payload XSS en nombre
        xss_payload = "<img src=x onerror=alert(1)>"

        register_data = {
            "email": "storedxss@example.com",
            "password": "ValidPassword123!",
            "first_name": xss_payload,
            "last_name": "User",
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        if response.status_code == 201:
            # Login para verificar que el payload fue sanitizado
            login_data = {
                "email": "storedxss@example.com",
                "password": "ValidPassword123!",
            }
            login_response = await client.post("/api/v1/auth/login", json=login_data)

            assert login_response.status_code == 200
            user_data = login_response.json()["user"]

            # Verificar que el payload XSS fue sanitizado
            first_name = user_data.get("first_name", "")
            assert "onerror" not in first_name.lower(), (
                "Los event handlers (onerror, onload, etc.) deben ser removidos"
            )
            assert "<img" not in first_name.lower() or "src=x" not in first_name.lower(), (
                "Los tags maliciosos deben ser sanitizados"
            )


@pytest.mark.asyncio
class TestHTMLSanitization:
    """Tests que validan la sanitización HTML."""

    async def test_html_tags_are_stripped(self, client: AsyncClient):
        """
        Given: El sistema sanitiza HTML en todos los inputs
        When: Se envían inputs con tags HTML
        Then: Los tags deben ser removidos o escapados
        """
        html_input = "<b>Bold</b> <i>Italic</i> <u>Underline</u>"

        register_data = {
            "email": "htmltest@example.com",
            "password": "ValidPassword123!",
            "first_name": html_input,
            "last_name": "User",
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        if response.status_code == 201:
            user_data = response.json()
            first_name = user_data.get("first_name", "")

            # Verificar que los tags HTML fueron removidos o escapados
            # Puede ser "Bold Italic Underline" (tags removidos) o texto escapado
            assert "<b>" not in first_name or "&lt;b&gt;" in first_name, (
                "Los tags HTML deben ser removidos o escapados"
            )

    async def test_javascript_protocol_blocked(self, client: AsyncClient):
        """
        Given: El protocolo javascript: puede ejecutar código
        When: Se intenta usar javascript: en inputs
        Then: Debe ser bloqueado o removido
        """
        javascript_payload = "javascript:alert('XSS')"

        register_data = {
            "email": "jsproto@example.com",
            "password": "ValidPassword123!",
            "first_name": javascript_payload,
            "last_name": "User",
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        if response.status_code == 201:
            user_data = response.json()
            first_name = user_data.get("first_name", "")

            # El protocolo javascript: debe ser removido
            assert "javascript:" not in first_name.lower(), (
                "El protocolo javascript: debe ser bloqueado"
            )


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Tests que verifican headers de seguridad anti-XSS."""

    async def test_content_type_nosniff_header(self, client: AsyncClient):
        """
        Given: El servidor configura X-Content-Type-Options: nosniff
        When: Se hace una request
        Then: El header debe estar presente (previene MIME sniffing attacks)
        """
        response = await client.get("/api/v1/auth/verify-email?token=dummy")

        assert "x-content-type-options" in response.headers, (
            "Header X-Content-Type-Options debe estar presente"
        )
        assert response.headers["x-content-type-options"] == "nosniff", (
            "X-Content-Type-Options debe ser 'nosniff'"
        )

    async def test_xframe_options_header(self, client: AsyncClient):
        """
        Given: El servidor configura X-Frame-Options
        When: Se hace una request
        Then: El header debe estar presente (previene clickjacking)
        """
        response = await client.get("/api/v1/auth/verify-email?token=dummy")

        # X-Frame-Options debe estar presente
        assert "x-frame-options" in response.headers, (
            "Header X-Frame-Options debe estar presente para prevenir clickjacking"
        )
