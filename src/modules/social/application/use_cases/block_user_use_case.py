"""Caso de Uso: Bloquear a un usuario."""

from src.modules.social.application.dto.friendship_dto import FriendshipResponseDTO
from src.modules.social.application.exceptions import AddresseeNotFoundError
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import SelfFriendRequestViolation
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class BlockUserUseCase:
    """
    Bloquea a otro usuario.

    Si ya existia una relacion (PENDING/ACCEPTED), transiciona a BLOCKED.
    Si no existia ninguna relacion, crea directamente un registro BLOCKED.
    Operacion idempotente si ya estaba bloqueado.
    """

    def __init__(
        self,
        uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, blocker_id_raw: str, blocked_id_raw: str) -> FriendshipResponseDTO:
        blocker_id = UserId(blocker_id_raw)
        blocked_id = UserId(blocked_id_raw)

        if blocker_id == blocked_id:
            raise SelfFriendRequestViolation("Cannot block yourself.")

        async with self._user_uow:
            blocked_user = await self._user_uow.users.find_by_id(blocked_id)
            if not blocked_user:
                raise AddresseeNotFoundError(f"User not found: {blocked_id_raw}")

        async with self._uow:
            friendship = await self._uow.friendships.find_by_pair(blocker_id, blocked_id)

            if friendship is None:
                friendship = Friendship.create_blocked(
                    id=FriendshipId.generate(),
                    blocker_id=blocker_id,
                    blocked_id=blocked_id,
                )
                await self._uow.friendships.add(friendship)
            elif not friendship.is_blocked():
                friendship.block(blocker_id)
                await self._uow.friendships.update(friendship)
            # Si ya estaba BLOCKED, la operacion es idempotente: no se modifica nada.

        return await self._build_response(friendship)

    async def _build_response(self, friendship: Friendship) -> FriendshipResponseDTO:
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
