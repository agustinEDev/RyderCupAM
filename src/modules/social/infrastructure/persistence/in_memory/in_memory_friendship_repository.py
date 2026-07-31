"""In-Memory Friendship Repository para testing."""

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    DuplicateFriendshipViolation,
)
from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryFriendshipRepository(FriendshipRepositoryInterface):
    """Implementacion en memoria del repositorio de amistades para testing."""

    def __init__(self):
        self._friendships: dict[FriendshipId, Friendship] = {}

    async def add(self, friendship: Friendship) -> None:
        # Mismo invariante que el indice unico `uq_friendship_pair` de la BD real:
        # una unica relacion (en cualquier estado) por pareja de usuarios, en
        # cualquier direccion. Permite simular en tests la misma race que
        # traduce SQLAlchemySocialUnitOfWork.flush() a DuplicateFriendshipViolation.
        pair = {friendship.requester_id, friendship.addressee_id}
        for existing in self._friendships.values():
            if {existing.requester_id, existing.addressee_id} == pair:
                raise DuplicateFriendshipViolation(
                    "A friendship between these users already exists."
                )
        self._friendships[friendship.id] = friendship

    async def update(self, friendship: Friendship) -> None:
        if friendship.id in self._friendships:
            self._friendships[friendship.id] = friendship

    async def remove(self, friendship: Friendship) -> None:
        self._friendships.pop(friendship.id, None)

    async def find_by_id(self, friendship_id: FriendshipId) -> Friendship | None:
        return self._friendships.get(friendship_id)

    async def find_by_pair(self, user_id_a: UserId, user_id_b: UserId) -> Friendship | None:
        for f in self._friendships.values():
            if {f.requester_id, f.addressee_id} == {user_id_a, user_id_b}:
                return f
        return None

    async def list_friends(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        results = [
            f
            for f in self._friendships.values()
            if f.status == FriendshipStatus.ACCEPTED and f.involves_user(user_id)
        ]
        results.sort(key=lambda x: x.updated_at, reverse=True)
        return results[offset : offset + limit]

    async def list_pending_received(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        results = [
            f
            for f in self._friendships.values()
            if f.status == FriendshipStatus.PENDING and f.addressee_id == user_id
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def list_pending_sent(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        results = [
            f
            for f in self._friendships.values()
            if f.status == FriendshipStatus.PENDING and f.requester_id == user_id
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def count_friends(self, user_id: UserId) -> int:
        return sum(
            1
            for f in self._friendships.values()
            if f.status == FriendshipStatus.ACCEPTED and f.involves_user(user_id)
        )

    async def count_pending_received(self, user_id: UserId) -> int:
        return sum(
            1
            for f in self._friendships.values()
            if f.status == FriendshipStatus.PENDING and f.addressee_id == user_id
        )

    async def count_pending_sent(self, user_id: UserId) -> int:
        return sum(
            1
            for f in self._friendships.values()
            if f.status == FriendshipStatus.PENDING and f.requester_id == user_id
        )

    async def are_friends(self, user_id_a: UserId, user_id_b: UserId) -> bool:
        friendship = await self.find_by_pair(user_id_a, user_id_b)
        return friendship is not None and friendship.status == FriendshipStatus.ACCEPTED
