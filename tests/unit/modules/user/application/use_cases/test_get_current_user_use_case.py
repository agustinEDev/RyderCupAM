"""
Tests para GetCurrentUserUseCase

Tests unitarios para el caso de uso de obtener usuario actual,
incluyendo campos auth_providers y has_password.
"""

import pytest

from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def use_case(uow):
    return GetCurrentUserUseCase(uow=uow)


@pytest.fixture
async def normal_user(uow):
    """Usuario registrado con email/password (sin OAuth)."""
    user = User.create(
        first_name="Normal",
        last_name="User",
        email_str="normal@example.com",
        plain_password="SecureP@ss123!",
    )
    async with uow:
        await uow.users.save(user)
    return user


@pytest.fixture
async def oauth_user(uow):
    """Usuario registrado via OAuth (sin password)."""
    user = User.create_from_oauth(
        first_name="OAuth",
        last_name="User",
        email_str="oauth@gmail.com",
    )
    async with uow:
        await uow.users.save(user)

    oauth = UserOAuthAccount.create(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-123",
        provider_email="oauth@gmail.com",
    )
    async with uow:
        await uow.oauth_accounts.save(oauth)

    return user


@pytest.fixture
async def user_with_google_linked(uow):
    """Usuario con password Y Google vinculado."""
    user = User.create(
        first_name="Both",
        last_name="Methods",
        email_str="both@example.com",
        plain_password="SecureP@ss123!",
    )
    async with uow:
        await uow.users.save(user)

    oauth = UserOAuthAccount.create(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-456",
        provider_email="both@gmail.com",
    )
    async with uow:
        await uow.oauth_accounts.save(oauth)

    return user


@pytest.mark.asyncio
class TestGetCurrentUserUseCase:
    """Tests para obtener usuario actual."""

    async def test_returns_user_dto(self, use_case, normal_user):
        """
        Test: Retorna UserResponseDTO para usuario existente.
        Given: Usuario registrado con email/password
        When: Se ejecuta con su ID
        Then: Retorna DTO con datos correctos
        """
        result = await use_case.execute(str(normal_user.id.value))

        assert result is not None
        assert result.email == "normal@example.com"
        assert result.first_name == "Normal"

    async def test_returns_none_for_nonexistent_user(self, use_case):
        """
        Test: Retorna None si el usuario no existe.
        Given: ID de usuario inexistente
        When: Se ejecuta con ese ID
        Then: Retorna None
        """
        result = await use_case.execute("00000000-0000-0000-0000-000000000000")

        assert result is None

    async def test_returns_none_for_invalid_id(self, use_case):
        """
        Test: Retorna None si el ID es inválido.
        Given: ID mal formado
        When: Se ejecuta con ese ID
        Then: Retorna None
        """
        result = await use_case.execute("not-a-valid-uuid")

        assert result is None


@pytest.mark.asyncio
class TestGetCurrentUserAuthProviders:
    """Tests para el campo auth_providers en la respuesta."""

    async def test_empty_auth_providers_for_normal_user(self, use_case, normal_user):
        """
        Test: auth_providers es [] para usuario sin OAuth.
        Given: Usuario registrado con email/password, sin Google vinculado
        When: Se obtiene el usuario actual
        Then: auth_providers es lista vacía
        """
        result = await use_case.execute(str(normal_user.id.value))

        assert result is not None
        assert result.auth_providers == []

    async def test_google_in_auth_providers_for_oauth_user(self, use_case, oauth_user):
        """
        Test: auth_providers incluye 'google' para usuario OAuth.
        Given: Usuario registrado via Google OAuth
        When: Se obtiene el usuario actual
        Then: auth_providers contiene 'google'
        """
        result = await use_case.execute(str(oauth_user.id.value))

        assert result is not None
        assert result.auth_providers == ["google"]

    async def test_google_in_auth_providers_for_linked_user(
        self, use_case, user_with_google_linked
    ):
        """
        Test: auth_providers incluye 'google' para usuario que vinculó Google.
        Given: Usuario con password que vinculó cuenta Google
        When: Se obtiene el usuario actual
        Then: auth_providers contiene 'google'
        """
        result = await use_case.execute(str(user_with_google_linked.id.value))

        assert result is not None
        assert result.auth_providers == ["google"]


@pytest.mark.asyncio
class TestGetCurrentUserHasPassword:
    """Tests para el campo has_password en la respuesta."""

    async def test_has_password_true_for_normal_user(self, use_case, normal_user):
        """
        Test: has_password es True para usuario con contraseña.
        Given: Usuario registrado con email/password
        When: Se obtiene el usuario actual
        Then: has_password es True
        """
        result = await use_case.execute(str(normal_user.id.value))

        assert result is not None
        assert result.has_password is True

    async def test_has_password_false_for_oauth_only_user(self, use_case, oauth_user):
        """
        Test: has_password es False para usuario OAuth sin contraseña.
        Given: Usuario registrado solo via Google OAuth
        When: Se obtiene el usuario actual
        Then: has_password es False
        """
        result = await use_case.execute(str(oauth_user.id.value))

        assert result is not None
        assert result.has_password is False

    async def test_has_password_true_for_linked_user(
        self, use_case, user_with_google_linked
    ):
        """
        Test: has_password es True para usuario con password y Google vinculado.
        Given: Usuario con password que también tiene Google vinculado
        When: Se obtiene el usuario actual
        Then: has_password es True (tiene ambos métodos)
        """
        result = await use_case.execute(str(user_with_google_linked.id.value))

        assert result is not None
        assert result.has_password is True
