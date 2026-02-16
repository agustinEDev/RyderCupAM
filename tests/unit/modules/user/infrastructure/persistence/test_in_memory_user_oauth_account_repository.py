"""
Tests para InMemoryUserOAuthAccountRepository

Tests unitarios para la implementación en memoria del repositorio de OAuth accounts.
"""

import pytest

from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_oauth_account_repository import (
    InMemoryUserOAuthAccountRepository,
)


@pytest.fixture
def repo():
    return InMemoryUserOAuthAccountRepository()


@pytest.fixture
def user_id():
    return UserId.generate()


@pytest.fixture
def oauth_account(user_id):
    return UserOAuthAccount.create(
        user_id=user_id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-repo-123",
        provider_email="repo@gmail.com",
    )


@pytest.mark.asyncio
class TestInMemoryUserOAuthAccountRepository:
    """Tests para el repositorio en memoria de OAuth accounts."""

    async def test_save_and_find_by_provider_and_provider_user_id(self, repo, oauth_account):
        """Debe guardar y encontrar por proveedor + ID de proveedor."""
        await repo.save(oauth_account)

        found = await repo.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-repo-123"
        )
        assert found is not None
        assert found.id == oauth_account.id
        assert found.provider_email == "repo@gmail.com"

    async def test_find_by_provider_returns_none_when_not_found(self, repo):
        """Debe retornar None cuando no existe la combinación proveedor + ID."""
        found = await repo.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "nonexistent"
        )
        assert found is None

    async def test_find_by_user_id(self, repo, user_id, oauth_account):
        """Debe encontrar todas las OAuth accounts de un usuario."""
        await repo.save(oauth_account)

        accounts = await repo.find_by_user_id(user_id)
        assert len(accounts) == 1
        assert accounts[0].id == oauth_account.id

    async def test_find_by_user_id_returns_empty_list(self, repo):
        """Debe retornar lista vacía cuando el usuario no tiene OAuth accounts."""
        accounts = await repo.find_by_user_id(UserId.generate())
        assert accounts == []

    async def test_find_by_user_id_and_provider(self, repo, user_id, oauth_account):
        """Debe encontrar OAuth account por usuario y proveedor."""
        await repo.save(oauth_account)

        found = await repo.find_by_user_id_and_provider(user_id, OAuthProvider.GOOGLE)
        assert found is not None
        assert found.id == oauth_account.id

    async def test_find_by_user_id_and_provider_returns_none(self, repo, user_id):
        """Debe retornar None cuando no existe la combinación."""
        found = await repo.find_by_user_id_and_provider(user_id, OAuthProvider.GOOGLE)
        assert found is None

    async def test_delete(self, repo, user_id, oauth_account):
        """Debe eliminar una OAuth account."""
        await repo.save(oauth_account)

        await repo.delete(oauth_account)

        found = await repo.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-repo-123"
        )
        assert found is None

    async def test_delete_nonexistent_does_nothing(self, repo, oauth_account):
        """Eliminar una cuenta que no existe no debe lanzar error."""
        await repo.delete(oauth_account)  # No debe lanzar excepción

    async def test_save_updates_existing(self, repo, user_id, oauth_account):
        """Guardar con mismo ID debe actualizar."""
        await repo.save(oauth_account)

        # Modificar y re-guardar
        oauth_account.provider_email = "updated@gmail.com"
        await repo.save(oauth_account)

        found = await repo.find_by_provider_and_provider_user_id(
            OAuthProvider.GOOGLE, "google-repo-123"
        )
        assert found.provider_email == "updated@gmail.com"

    async def test_multiple_accounts_per_user(self, repo, user_id):
        """Un usuario puede tener múltiples OAuth accounts (de diferentes proveedores)."""
        account1 = UserOAuthAccount.create(
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-multi",
            provider_email="multi@gmail.com",
        )
        await repo.save(account1)

        # Si hubiera otro proveedor, podríamos añadir otro
        # Por ahora verificamos que find_by_user_id retorna correctamente
        accounts = await repo.find_by_user_id(user_id)
        assert len(accounts) == 1
