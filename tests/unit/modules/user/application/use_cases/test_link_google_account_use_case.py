"""
Tests para LinkGoogleAccountUseCase

Tests unitarios para el caso de uso de vincular cuenta Google a usuario existente.
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.oauth_dto import LinkGoogleAccountRequestDTO
from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    LinkGoogleAccountUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def google_oauth_service():
    return AsyncMock()


@pytest.fixture
def google_user_info():
    return GoogleUserInfo(
        google_user_id="google-link-123",
        email="link@gmail.com",
        first_name="Link",
        last_name="User",
    )


@pytest.fixture
def use_case(uow, google_oauth_service):
    return LinkGoogleAccountUseCase(
        uow=uow,
        google_oauth_service=google_oauth_service,
    )


@pytest.fixture
async def existing_user(uow):
    user = User.create(
        first_name="Existing",
        last_name="User",
        email_str="existing@example.com",
        plain_password="V@l1dP@ss123!",
    )
    async with uow:
        await uow.users.save(user)
    return user


@pytest.mark.asyncio
class TestLinkGoogleAccountUseCase:
    """Tests para vincular cuenta Google."""

    async def test_link_google_account_successfully(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Debe vincular Google account exitosamente."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        response = await use_case.execute(request, str(existing_user.id.value))

        assert response.message == "Google account linked successfully"
        assert response.provider == "google"
        assert response.provider_email == "link@gmail.com"

        # Verificar que se creó la OAuth account
        oauth = await uow.oauth_accounts.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-link-123"
        )
        assert oauth is not None
        assert oauth.user_id == existing_user.id

    async def test_link_fails_when_google_account_already_linked_to_another_user(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Debe fallar si la cuenta Google ya está vinculada a otro usuario."""
        # Vincular a otro usuario primero
        other_user_id = UserId.generate()
        other_oauth = UserOAuthAccount.create(
            user_id=other_user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-link-123",
            provider_email="other@gmail.com",
        )
        async with uow:
            await uow.oauth_accounts.save(other_oauth)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        with pytest.raises(ValueError, match="already linked to another user"):
            await use_case.execute(request, str(existing_user.id.value))

    async def test_link_fails_when_user_already_has_google(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Debe fallar si el usuario ya tiene una cuenta Google vinculada."""
        # Vincular Google al usuario actual
        existing_oauth = UserOAuthAccount.create(
            user_id=existing_user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-old-456",
            provider_email="old@gmail.com",
        )
        async with uow:
            await uow.oauth_accounts.save(existing_oauth)

        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        with pytest.raises(ValueError, match="already have a Google account linked"):
            await use_case.execute(request, str(existing_user.id.value))

    async def test_link_propagates_oauth_service_error(
        self, use_case, google_oauth_service, existing_user
    ):
        """Debe propagar errores del servicio de Google."""
        google_oauth_service.exchange_code_for_user_info.side_effect = ValueError(
            "Invalid authorization code"
        )

        request = LinkGoogleAccountRequestDTO(authorization_code="bad-code")
        with pytest.raises(ValueError, match="Invalid authorization code"):
            await use_case.execute(request, str(existing_user.id.value))

    async def test_link_creates_oauth_account_with_correct_data(
        self, use_case, uow, google_oauth_service, google_user_info, existing_user
    ):
        """Verifica que la OAuth account se crea con datos correctos."""
        google_oauth_service.exchange_code_for_user_info.return_value = google_user_info

        request = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        await use_case.execute(request, str(existing_user.id.value))

        oauth = await uow.oauth_accounts.find_by_user_id_and_provider(
            existing_user.id, OAuthProvider.GOOGLE
        )
        assert oauth is not None
        assert oauth.provider == OAuthProvider.GOOGLE
        assert oauth.provider_user_id == "google-link-123"
        assert oauth.provider_email == "link@gmail.com"
        assert oauth.user_id == existing_user.id
