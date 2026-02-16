"""
SQLAlchemy User OAuth Account Repository.

Implementación del repositorio de OAuth accounts usando SQLAlchemy (async).
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.repositories.user_oauth_account_repository_interface import (
    UserOAuthAccountRepositoryInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.user_oauth_account_mapper import (
    user_oauth_accounts_table,
)


class SQLAlchemyUserOAuthAccountRepository(UserOAuthAccountRepositoryInterface):
    """Implementación SQLAlchemy del repositorio de OAuth accounts."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, oauth_account: UserOAuthAccount) -> None:
        self._session.add(oauth_account)
        await self._session.flush()

    async def find_by_provider_and_provider_user_id(
        self, provider: OAuthProvider, provider_user_id: str
    ) -> UserOAuthAccount | None:
        stmt = (
            select(UserOAuthAccount)
            .where(user_oauth_accounts_table.c.provider == provider.value)
            .where(user_oauth_accounts_table.c.provider_user_id == provider_user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def find_by_user_id(self, user_id: UserId) -> list[UserOAuthAccount]:
        stmt = select(UserOAuthAccount).where(
            user_oauth_accounts_table.c.user_id == str(user_id.value)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_user_id_and_provider(
        self, user_id: UserId, provider: OAuthProvider
    ) -> UserOAuthAccount | None:
        stmt = (
            select(UserOAuthAccount)
            .where(user_oauth_accounts_table.c.user_id == str(user_id.value))
            .where(user_oauth_accounts_table.c.provider == provider.value)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def delete(self, oauth_account: UserOAuthAccount) -> None:
        stmt = delete(user_oauth_accounts_table).where(
            user_oauth_accounts_table.c.id == str(oauth_account.id.value)
        )
        await self._session.execute(stmt)
        await self._session.flush()
