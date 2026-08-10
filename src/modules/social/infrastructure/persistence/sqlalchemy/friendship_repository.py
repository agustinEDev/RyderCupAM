"""Friendship Repository - SQLAlchemy Implementation."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.social.infrastructure.persistence.mappers.friendship_mapper import (
    friendships_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyFriendshipRepository(FriendshipRepositoryInterface):
    """Implementacion asincrona del repositorio de amistades con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, friendship: Friendship) -> None:
        self._session.add(friendship)

    async def update(self, friendship: Friendship) -> None:
        self._session.add(friendship)

    async def remove(self, friendship: Friendship) -> None:
        await self._session.delete(friendship)

    async def find_by_id(self, friendship_id: FriendshipId) -> Friendship | None:
        return await self._session.get(Friendship, friendship_id)

    async def find_by_pair(self, user_id_a: UserId, user_id_b: UserId) -> Friendship | None:
        stmt = select(Friendship).where(
            or_(
                and_(
                    Friendship._requester_id == user_id_a,
                    Friendship._addressee_id == user_id_b,
                ),
                and_(
                    Friendship._requester_id == user_id_b,
                    Friendship._addressee_id == user_id_a,
                ),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_friends(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        stmt = (
            select(Friendship)
            .where(
                and_(
                    Friendship._status == FriendshipStatus.ACCEPTED,
                    or_(
                        Friendship._requester_id == user_id,
                        Friendship._addressee_id == user_id,
                    ),
                )
            )
            .order_by(Friendship._updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_received(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        stmt = (
            select(Friendship)
            .where(
                and_(
                    Friendship._status == FriendshipStatus.PENDING,
                    Friendship._addressee_id == user_id,
                )
            )
            .order_by(Friendship._created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_sent(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        stmt = (
            select(Friendship)
            .where(
                and_(
                    Friendship._status == FriendshipStatus.PENDING,
                    Friendship._requester_id == user_id,
                )
            )
            .order_by(Friendship._created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_friends(self, user_id: UserId) -> int:
        stmt = (
            select(func.count())
            .select_from(Friendship)
            .where(
                and_(
                    Friendship._status == FriendshipStatus.ACCEPTED,
                    or_(
                        Friendship._requester_id == user_id,
                        Friendship._addressee_id == user_id,
                    ),
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_pending_received(self, user_id: UserId) -> int:
        stmt = (
            select(func.count())
            .select_from(Friendship)
            .where(
                and_(
                    Friendship._status == FriendshipStatus.PENDING,
                    Friendship._addressee_id == user_id,
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_pending_sent(self, user_id: UserId) -> int:
        stmt = (
            select(func.count())
            .select_from(Friendship)
            .where(
                and_(
                    Friendship._status == FriendshipStatus.PENDING,
                    Friendship._requester_id == user_id,
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def are_friends(self, user_id_a: UserId, user_id_b: UserId) -> bool:
        friendship = await self.find_by_pair(user_id_a, user_id_b)
        return friendship is not None and friendship.status == FriendshipStatus.ACCEPTED

    async def find_friend_ids(self, user_id: UserId) -> list[UserId]:
        """
        Los ids de los amigos aceptados, en una sola consulta.

        Se piden las dos columnas y se descarta la propia: la amistad se guarda
        una vez con quien la pidio y quien la recibio, y el usuario puede estar
        en cualquiera de los dos lados.
        """
        stmt = select(
            friendships_table.c.requester_id, friendships_table.c.addressee_id
        ).where(
            and_(
                friendships_table.c.status == FriendshipStatus.ACCEPTED,
                or_(
                    friendships_table.c.requester_id == user_id,
                    friendships_table.c.addressee_id == user_id,
                ),
            )
        )
        result = await self._session.execute(stmt)
        return [
            addressee_id if requester_id == user_id else requester_id
            for requester_id, addressee_id in result.all()
        ]
