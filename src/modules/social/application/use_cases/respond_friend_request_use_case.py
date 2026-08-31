"""Caso de Uso: Responder a una Solicitud de Amistad (ACCEPT/DECLINE)."""

from src.modules.social.application.dto.friendship_dto import (
    FriendshipResponseDTO,
    RespondFriendRequestRequestDTO,
)
from src.modules.social.application.exceptions import (
    FriendshipNotFoundError,
    NotAddresseeError,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class RespondFriendRequestUseCase:
    """Permite al destinatario aceptar o rechazar una solicitud de amistad."""

    def __init__(
        self,
        uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: RespondFriendRequestRequestDTO) -> FriendshipResponseDTO:
        friendship_id = FriendshipId(request.friendship_id)
        current_user_id = UserId(request.user_id)
        action = request.action.upper()

        if action not in ("ACCEPT", "DECLINE"):
            raise ValueError(f"Invalid action: {action}. Must be ACCEPT or DECLINE.")

        async with self._uow:
            friendship = await self._uow.friendships.find_by_id(friendship_id)
            if not friendship:
                raise FriendshipNotFoundError(f"Friendship request not found: {friendship_id}")

            if friendship.addressee_id != current_user_id:
                raise NotAddresseeError("You are not the addressee of this friend request.")

            if action == "ACCEPT":
                friendship.accept()
            else:
                friendship.decline()

            await self._uow.friendships.update(friendship)

        return await self._build_response(friendship)

    async def _build_response(self, friendship: Friendship) -> FriendshipResponseDTO:
        async with self._user_uow:
            requester = await self._user_uow.users.find_by_id(friendship.requester_id)
            addressee = await self._user_uow.users.find_by_id(friendship.addressee_id)
            # `display_name`: el alias de quien lo tenga, y si no su nombre
            # completo (BE #239). Estos dos campos son «nombre para enseñar»
            requester_name = requester.display_name if requester else "Unknown"
            addressee_name = addressee.display_name if addressee else "Unknown"

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
