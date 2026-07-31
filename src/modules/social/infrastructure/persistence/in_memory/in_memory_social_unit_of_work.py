"""In-Memory Social Unit of Work para testing."""

from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_friendship_repository import (
    InMemoryFriendshipRepository,
)


class InMemorySocialUnitOfWork(SocialUnitOfWorkInterface):
    """Implementacion en memoria de la Unit of Work del modulo Social para testing."""

    def __init__(self):
        self._friendships = InMemoryFriendshipRepository()
        self.committed = False

    @property
    def friendships(self) -> FriendshipRepositoryInterface:
        return self._friendships

    async def __aenter__(self):
        self.committed = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            try:
                await self.commit()
            except Exception:
                await self.rollback()
                raise

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False

    async def flush(self) -> None:
        pass

    def is_active(self) -> bool:
        return True
