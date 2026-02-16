"""
Tests para GoogleLoginUseCase

Tests unitarios para el caso de uso de login/registro con Google OAuth.
Verifica los 3 flujos: OAuth existente, auto-link, auto-register.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.device_dto import RegisterDeviceResponseDTO
from src.modules.user.application.dto.oauth_dto import GoogleLoginRequestDTO
from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
)
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleLoginUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.exceptions import AccountLockedException
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def token_service():
    return JWTTokenService()


@pytest.fixture
def google_oauth_service():
    mock = AsyncMock()
    return mock


@pytest.fixture
def register_device_use_case():
    mock = AsyncMock()
    mock.execute.return_value = RegisterDeviceResponseDTO(
        device_id="550e8400-e29b-41d4-a716-446655440099",
        is_new_device=True,
        message="New device registered",
        set_device_cookie=True,
    )
    return mock


@pytest.fixture
def google_user_info():
    return GoogleUserInfo(
        google_user_id="google-id-12345",
        email="oauth@example.com",
        first_name="Google",
        last_name="User",
        email_verified=True,
        picture_url="https://lh3.googleusercontent.com/photo.jpg",
    )


@pytest.fixture
def use_case(uow, token_service, google_oauth_service, register_device_use_case):
    return GoogleLoginUseCase(
        uow=uow,
        token_service=token_service,
        google_oauth_service=google_oauth_service,
        register_device_use_case=register_device_use_case,
    )


@pytest.fixture
def login_request():
    return GoogleLoginRequestDTO(
        authorization_code="valid-auth-code",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Test",
        device_id_from_cookie=None,
    )


@pytest.mark.asyncio
class TestGoogleLoginUseCaseAutoRegister:
    """Tests para flujo 3: usuario nuevo → auto-register."""

    async def test_auto_register_creates_new_user(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe crear usuario nuevo cuando no existe en el sistema."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response is not None
        assert response.is_new_user is True
        assert response.user.email == "oauth@example.com"
        assert response.user.first_name == "Google"
        assert response.user.last_name == "User"
        assert response.token_type == "bearer"
        assert response.access_token is not None
        assert response.refresh_token is not None

    async def test_auto_register_user_has_no_password(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """El usuario creado desde OAuth no debe tener password."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        # Buscar usuario en el repo
        from src.modules.user.domain.value_objects.email import Email

        user = await uow.users.find_by_email(Email("oauth@example.com"))
        assert user is not None
        assert user.has_password is False

    async def test_auto_register_user_email_verified(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """El usuario OAuth debe tener email verificado."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        from src.modules.user.domain.value_objects.email import Email

        user = await uow.users.find_by_email(Email("oauth@example.com"))
        assert user is not None
        assert user.email_verified is True

    async def test_auto_register_creates_oauth_account(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe crear OAuthAccount vinculado al nuevo usuario."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        oauth = await uow.oauth_accounts.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-id-12345"
        )
        assert oauth is not None
        assert oauth.provider_email == "oauth@example.com"

    async def test_auto_register_device_registration(
        self, use_case, google_oauth_service, google_user_info, login_request, register_device_use_case
    ):
        """Debe registrar dispositivo y retornar device_id."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response.device_id == "550e8400-e29b-41d4-a716-446655440099"
        assert response.should_set_device_cookie is True
        register_device_use_case.execute.assert_called_once()


@pytest.mark.asyncio
class TestGoogleLoginUseCaseExistingOAuth:
    """Tests para flujo 1: OAuth account existente → login directo."""

    async def test_existing_oauth_user_login(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe hacer login directo cuando ya existe OAuth account."""
        # Crear usuario y OAuth account existentes
        user = User.create_from_oauth(
            first_name="Existing",
            last_name="User",
            email_str="oauth@example.com",
        )
        async with uow:
            await uow.users.save(user)

        oauth_account = UserOAuthAccount.create(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-id-12345",
            provider_email="oauth@example.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth_account)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response is not None
        assert response.is_new_user is False
        assert response.user.email == "oauth@example.com"
        assert response.user.first_name == "Existing"

    async def test_existing_oauth_user_not_found_raises(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe lanzar error si OAuth account existe pero usuario no."""
        # Crear solo OAuth account sin usuario
        fake_user_id = UserId.generate()
        oauth_account = UserOAuthAccount.create(
            user_id=fake_user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-id-12345",
            provider_email="orphan@example.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth_account)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        with pytest.raises(ValueError, match="User associated with OAuth account not found"):
            await use_case.execute(login_request)


@pytest.mark.asyncio
class TestGoogleLoginUseCaseAutoLink:
    """Tests para flujo 2: usuario email existente → auto-link."""

    async def test_auto_link_existing_email_user(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe auto-link cuando usuario existe por email pero sin OAuth."""
        user = User.create(
            first_name="Email",
            last_name="User",
            email_str="oauth@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert response.is_new_user is False
        assert response.user.first_name == "Email"

        # Verificar que se creó la OAuth account
        oauth = await uow.oauth_accounts.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-id-12345"
        )
        assert oauth is not None

    async def test_auto_link_verifies_unverified_email(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe verificar email si el usuario existente no lo tiene verificado."""
        user = User.create(
            first_name="Unverified",
            last_name="User",
            email_str="oauth@example.com",
            plain_password="V@l1dP@ss123!",
        )
        assert user.email_verified is False
        async with uow:
            await uow.users.save(user)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        await use_case.execute(login_request)

        # Verificar que ahora tiene email verificado
        from src.modules.user.domain.value_objects.email import Email

        updated_user = await uow.users.find_by_email(Email("oauth@example.com"))
        assert updated_user.email_verified is True


@pytest.mark.asyncio
class TestGoogleLoginUseCaseLockout:
    """Tests para protección de cuenta bloqueada."""

    async def test_locked_account_raises_exception(
        self, use_case, uow, google_oauth_service, google_user_info, login_request
    ):
        """Debe lanzar AccountLockedException si la cuenta está bloqueada."""
        user = User.create_from_oauth(
            first_name="Locked",
            last_name="User",
            email_str="oauth@example.com",
        )
        # Bloquear la cuenta
        from datetime import timedelta

        user.locked_until = datetime.now() + timedelta(minutes=30)
        user.failed_login_attempts = 10

        async with uow:
            await uow.users.save(user)

        oauth_account = UserOAuthAccount.create(
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-id-12345",
            provider_email="oauth@example.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth_account)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        with pytest.raises(AccountLockedException):
            await use_case.execute(login_request)


@pytest.mark.asyncio
class TestGoogleLoginUseCaseTokenGeneration:
    """Tests para generación de tokens."""

    async def test_generates_access_and_refresh_tokens(
        self, use_case, google_oauth_service, google_user_info, login_request
    ):
        """Debe generar tokens JWT válidos."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        response = await use_case.execute(login_request)

        assert len(response.access_token) > 0
        assert len(response.refresh_token) > 0
        assert response.csrf_token is not None
        assert len(response.csrf_token) > 0

    async def test_invalid_code_raises_value_error(
        self, use_case, google_oauth_service, login_request
    ):
        """Debe propagar ValueError cuando el código es inválido."""
        google_oauth_service.exchange_code_for_user_info.side_effect = ValueError(
            "Invalid or expired Google authorization code"
        )

        with pytest.raises(ValueError, match="Invalid or expired"):
            await use_case.execute(login_request)

    async def test_no_device_registration_without_user_agent(
        self, use_case, uow, google_oauth_service, google_user_info, register_device_use_case
    ):
        """No debe registrar dispositivo si falta user_agent."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = GoogleLoginRequestDTO(
            authorization_code="valid-code",
            ip_address=None,
            user_agent=None,
        )

        response = await use_case.execute(request)

        assert response.device_id is None
        assert response.should_set_device_cookie is False
        register_device_use_case.execute.assert_not_called()
