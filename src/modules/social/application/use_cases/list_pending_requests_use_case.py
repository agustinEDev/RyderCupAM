"""Caso de Uso: Listar solicitudes de amistad pendientes (recibidas o enviadas)."""

from src.modules.social.application.dto.friendship_dto import (
    FriendshipResponseDTO,
    PaginatedFriendshipResponseDTO,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class ListPendingRequestsUseCase:
    """Lista las solicitudes de amistad PENDING del usuario, recibidas o enviadas."""

    def __init__(
        self,
        uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self,
        user_id_raw: str,
        direction: str = "received",
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedFriendshipResponseDTO:
        if direction not in ("received", "sent"):
            raise ValueError(f"Invalid direction: {direction}. Must be 'received' or 'sent'.")

        user_id = UserId(user_id_raw)
        offset = (page - 1) * limit

        async with self._uow:
            if direction == "received":
                friendships = await self._uow.friendships.list_pending_received(
                    user_id, limit=limit, offset=offset
                )
                total_count = await self._uow.friendships.count_pending_received(user_id)
            else:
                friendships = await self._uow.friendships.list_pending_sent(
                    user_id, limit=limit, offset=offset
                )
                total_count = await self._uow.friendships.count_pending_sent(user_id)

        items = [await self._to_dto(f) for f in friendships]

        return PaginatedFriendshipResponseDTO(
            friendships=items,
            total_count=total_count,
            page=page,
            limit=limit,
        )

    async def _to_dto(self, friendship: Friendship) -> FriendshipResponseDTO:
        async with self._user_uow:
            requester = await self._user_uow.users.find_by_id(friendship.requester_id)
            addressee = await self._user_uow.users.find_by_id(friendship.addressee_id)
            requester_name = (
                f"{requester.first_name} {requester.last_name}" if requester else "Unknown"
            )
            addressee_name = (
                f"{addressee.first_name} {addressee.last_name}" if addressee else "Unknown"
            )

        return FriendshipResponseDTO(
            id=friendship.id.value,
            requester_id=friendship.requester_id.value,
            requester_name=requester_name,
            addressee_id=friendship.addressee_id.value,
            addressee_name=addressee_name,
            status=friendship.status.value,
            responded_at=friendship.responded_at,
            created_at=friendship.created_at,
            updated_at=friendship.updated_at,
        )
