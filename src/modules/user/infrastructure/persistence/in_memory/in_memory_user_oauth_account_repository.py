"""
In-Memory User OAuth Account Repository para testing.
"""

from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.repositories.user_oauth_account_repository_interface import (
    UserOAuthAccountRepositoryInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryUserOAuthAccountRepository(UserOAuthAccountRepositoryInterface):
    """Implementación en memoria del repositorio de OAuth accounts para tests."""

    def __init__(self):
        self._accounts: dict[str, UserOAuthAccount] = {}

    async def save(self, oauth_account: UserOAuthAccount) -> None:
        self._accounts[str(oauth_account.id.value)] = oauth_account

    async def find_by_provider_and_provider_user_id(
        self, provider: OAuthProvider, provider_user_id: str
    ) -> UserOAuthAccount | None:
        for account in self._accounts.values():
            if account.provider == provider and account.provider_user_id == provider_user_id:
                return account
        return None

    async def find_by_user_id(self, user_id: UserId) -> list[UserOAuthAccount]:
        return [a for a in self._accounts.values() if a.user_id == user_id]

    async def find_by_user_id_and_provider(
        self, user_id: UserId, provider: OAuthProvider
    ) -> UserOAuthAccount | None:
        for account in self._accounts.values():
            if account.user_id == user_id and account.provider == provider:
                return account
        return None

    async def delete(self, oauth_account: UserOAuthAccount) -> None:
        key = str(oauth_account.id.value)
        if key in self._accounts:
            del self._accounts[key]
