"""
Tests para GoogleOAuthService

Tests unitarios para el adaptador de Google OAuth usando httpx mock.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
)
from src.modules.user.infrastructure.external.google_oauth_service import (
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
    HTTP_OK,
    GoogleOAuthService,
)


@pytest.fixture
def service():
    return GoogleOAuthService()


@pytest.fixture
def mock_token_response():
    """Mock response del token endpoint de Google."""
    response = MagicMock()
    response.status_code = HTTP_OK
    response.json.return_value = {
        "access_token": "ya29.test-access-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid email profile",
        "id_token": "eyJhbGciOiJSUzI1NiJ9.test",
    }
    return response


@pytest.fixture
def mock_userinfo_response():
    """Mock response del userinfo endpoint de Google."""
    response = MagicMock()
    response.status_code = HTTP_OK
    response.json.return_value = {
        "sub": "google-12345",
        "email": "user@gmail.com",
        "email_verified": True,
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }
    return response


@pytest.mark.asyncio
class TestGoogleOAuthService:
    """Tests para el servicio de Google OAuth."""

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_for_user_info_success(
        self, mock_client_class, service, mock_token_response, mock_userinfo_response
    ):
        """Debe retornar GoogleUserInfo con datos correctos."""
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_token_response
        mock_client.get.return_value = mock_userinfo_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await service.exchange_code_for_user_info("valid-auth-code")

        assert isinstance(result, GoogleUserInfo)
        assert result.google_user_id == "google-12345"
        assert result.email == "user@gmail.com"
        assert result.first_name == "Test"
        assert result.last_name == "User"
        assert result.picture_url == "https://lh3.googleusercontent.com/photo.jpg"

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_fails_on_token_error(self, mock_client_class, service):
        """Debe lanzar ValueError cuando el token exchange falla."""
        mock_client = AsyncMock()
        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Invalid grant"
        mock_client.post.return_value = error_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Invalid or expired"):
            await service.exchange_code_for_user_info("bad-code")

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_fails_on_missing_access_token(self, mock_client_class, service):
        """Debe lanzar ValueError cuando Google no retorna access_token."""
        mock_client = AsyncMock()
        token_response = MagicMock()
        token_response.status_code = HTTP_OK
        token_response.json.return_value = {"token_type": "Bearer"}  # Sin access_token
        mock_client.post.return_value = token_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="did not return an access token"):
            await service.exchange_code_for_user_info("code-no-token")

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_fails_on_userinfo_error(
        self, mock_client_class, service, mock_token_response
    ):
        """Debe lanzar ValueError cuando el userinfo endpoint falla."""
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_token_response

        userinfo_error = MagicMock()
        userinfo_error.status_code = 401
        mock_client.get.return_value = userinfo_error

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to retrieve user information"):
            await service.exchange_code_for_user_info("code-userinfo-fail")

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_fails_on_missing_required_fields(
        self, mock_client_class, service, mock_token_response
    ):
        """Debe lanzar ValueError cuando falta sub o email en userinfo."""
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_token_response

        userinfo_response = MagicMock()
        userinfo_response.status_code = HTTP_OK
        userinfo_response.json.return_value = {
            "given_name": "Test",
            "family_name": "User",
            # Falta sub y email
        }
        mock_client.get.return_value = userinfo_response

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="missing required fields"):
            await service.exchange_code_for_user_info("code-missing-fields")

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_handles_missing_optional_fields(
        self, mock_client_class, service, mock_token_response
    ):
        """
        Sin nombre en el perfil, el nombre sale del email y NUNCA vacío.

        Este test afirmaba que el nombre y el apellido quedaban en `""`, y con
        eso daba por bueno el defecto: el registro se cerraba con el nombre en
        blanco, el cliente rechazaba la respuesta al pintarla y la cuenta
        quedaba creada sin poder entrar nunca. Ver la issue #227.
        """
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_token_response

        userinfo_response = MagicMock()
        userinfo_response.status_code = HTTP_OK
        userinfo_response.json.return_value = {
            "sub": "google-minimal",
            "email": "minimal@gmail.com",
            # Sin given_name, family_name, picture
        }
        mock_client.get.return_value = userinfo_response

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await service.exchange_code_for_user_info("code-minimal")

        assert result.google_user_id == "google-minimal"
        assert result.email == "minimal@gmail.com"
        assert result.first_name == "minimal"
        assert result.last_name == "minimal"
        assert result.picture_url is None

    @patch("src.modules.user.infrastructure.external.google_oauth_service.httpx.AsyncClient")
    async def test_exchange_code_calls_correct_urls(
        self, mock_client_class, service, mock_token_response, mock_userinfo_response
    ):
        """Debe llamar a los URLs correctos de Google."""
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_token_response
        mock_client.get.return_value = mock_userinfo_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        await service.exchange_code_for_user_info("test-code")

        # Verificar que se llamó al token URL
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == GOOGLE_TOKEN_URL

        # Verificar que se llamó al userinfo URL con el access token
        mock_client.get.assert_called_once()
        get_call_args = mock_client.get.call_args
        assert get_call_args[0][0] == GOOGLE_USERINFO_URL
        assert "Bearer ya29.test-access-token" in str(get_call_args)


class TestResolveNames:
    """
    De dónde sale el nombre cuando Google no lo manda entero (issue #227).

    Google solo manda `given_name` y `family_name` con el nombre estructurado.
    Lo que se guardaba antes en su lugar —cadena vacía— dejaba la cuenta creada
    y sin poder entrar nunca, porque el cliente exige los dos campos.
    """

    def test_uses_the_structured_name_when_google_sends_it(self):
        assert GoogleOAuthService._resolve_names(
            {"given_name": "Ada", "family_name": "Lovelace"}, "ada@example.com"
        ) == ("Ada", "Lovelace")

    def test_splits_the_full_name_when_the_structured_one_is_missing(self):
        """El primer término es el nombre y el resto los apellidos."""
        assert GoogleOAuthService._resolve_names(
            {"name": "Ada Lovelace King"}, "ada@example.com"
        ) == ("Ada", "Lovelace King")

    def test_falls_back_to_the_email_for_the_surname_of_a_single_name_account(self):
        """El caso real del reporte: cuenta con un solo nombre y sin apellido."""
        assert GoogleOAuthService._resolve_names(
            {"given_name": "Ada", "name": "Ada"}, "lovelace@example.com"
        ) == ("Ada", "lovelace")

    def test_falls_back_to_the_email_when_there_is_no_name_at_all(self):
        assert GoogleOAuthService._resolve_names({}, "ada.lovelace@example.com") == (
            "ada.lovelace",
            "ada.lovelace",
        )

    def test_never_returns_an_empty_field(self):
        """
        Un email sin parte local dejaría el mismo hueco que se está cerrando.
        Ninguna combinación puede devolver una cadena vacía: es lo único que
        el cliente no acepta.
        """
        for userinfo, email in [
            ({}, "@example.com"),
            ({"given_name": "   ", "family_name": "   "}, "@example.com"),
            ({"name": "   "}, "@example.com"),
        ]:
            first_name, last_name = GoogleOAuthService._resolve_names(userinfo, email)
            assert first_name and last_name, (userinfo, email)

    def test_ignores_blank_padding_around_the_names(self):
        assert GoogleOAuthService._resolve_names(
            {"given_name": "  Ada  ", "family_name": "  Lovelace  "}, "ada@example.com"
        ) == ("Ada", "Lovelace")

