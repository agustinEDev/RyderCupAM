"""In-Memory Social Unit of Work para testing."""

from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
)
from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.repositories.profile_photo_repository_interface import (
    ProfilePhotoRepositoryInterface,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_activity_event_repository import (
    InMemoryActivityEventRepository,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_friendship_repository import (
    InMemoryFriendshipRepository,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_profile_photo_repository import (
    InMemoryProfilePhotoRepository,
)


class InMemorySocialUnitOfWork(SocialUnitOfWorkInterface):
    """Implementacion en memoria de la Unit of Work del modulo Social para testing."""

    def __init__(self):
        self._friendships = InMemoryFriendshipRepository()
        self._activity_events = InMemoryActivityEventRepository()
        self._profile_photos = InMemoryProfilePhotoRepository()
        self.committed = False

    @property
    def friendships(self) -> FriendshipRepositoryInterface:
        return self._friendships

    @property
    def activity_events(self) -> ActivityEventRepositoryInterface:
        return self._activity_events

    @property
    def profile_photos(self) -> ProfilePhotoRepositoryInterface:
        return self._profile_photos

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
