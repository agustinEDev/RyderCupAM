"""Social Unit of Work - SQLAlchemy Implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.friendship_repository import (
    SQLAlchemyFriendshipRepository,
)


class SQLAlchemySocialUnitOfWork(SocialUnitOfWorkInterface):
    """Implementacion asincrona de la Unit of Work del modulo Social con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._friendships = SQLAlchemyFriendshipRepository(session)

    @property
    def friendships(self) -> FriendshipRepositoryInterface:
        return self._friendships

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def flush(self) -> None:
        await self._session.flush()

    def is_active(self) -> bool:
        return self._session.is_active
