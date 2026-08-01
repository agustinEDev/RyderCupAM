"""Caso de Uso: Enviar una Solicitud de Amistad."""

import logging

from src.modules.social.application.dto.friendship_dto import (
    FriendshipResponseDTO,
    SendFriendRequestRequestDTO,
)
from src.modules.social.application.exceptions import AddresseeNotFoundError
from src.modules.social.application.ports.social_email_service_interface import (
    ISocialEmailService,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    BlockedUserViolation,
    DuplicateFriendRequestViolation,
    SelfFriendRequestViolation,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.security.email_masking import mask_email as _mask_email

logger = logging.getLogger(__name__)


class SendFriendRequestUseCase:
    """Envia una solicitud de amistad de un usuario a otro."""

    def __init__(
        self,
        uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        email_service: ISocialEmailService | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._email_service = email_service

    async def execute(self, request: SendFriendRequestRequestDTO) -> FriendshipResponseDTO:
        requester_id = UserId(request.requester_id)
        addressee_id = UserId(request.addressee_id)

        if requester_id == addressee_id:
            raise SelfFriendRequestViolation("Cannot send a friend request to yourself.")

        async with self._user_uow:
            addressee_user = await self._user_uow.users.find_by_id(addressee_id)
            if not addressee_user:
                raise AddresseeNotFoundError(f"User not found: {request.addressee_id}")

        async with self._uow:
            existing = await self._uow.friendships.find_by_pair(requester_id, addressee_id)

            if existing is not None:
                if existing.is_blocked():
                    raise BlockedUserViolation(
                        "Cannot send a friend request: a block exists between both users."
                    )
                if existing.is_pending() or existing.is_accepted():
                    raise DuplicateFriendRequestViolation(
                        "A friendship or pending request already exists between both users."
                    )
                # DECLINED es terminal: se elimina el registro anterior y se reenvia.
                # Flush explicito: el indice unico uq_friendship_pair (LEAST/GREATEST)
                # rechaza el INSERT si el DELETE no se ha aplicado ya en BD (SQLAlchemy
                # ordena inserts antes que deletes en el flush por defecto).
                await self._uow.friendships.remove(existing)
                await self._uow.flush()

            friendship = Friendship.create(
                id=FriendshipId.generate(),
                requester_id=requester_id,
                addressee_id=addressee_id,
            )
            await self._uow.friendships.add(friendship)

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

        # Enviar email de notificacion (fuera de la transaccion, no bloquea la creacion)
        if self._email_service and addressee and addressee.email:
            addressee_email = str(addressee.email)
            try:
                await self._email_service.send_friend_request_email(
                    to_email=addressee_email,
                    addressee_name=addressee_name,
                    requester_name=requester_name,
                )
            except Exception as e:
                logger.warning(
                    "Failed to send friend request email to %s: %s",
                    _mask_email(addressee_email),
                    str(e),
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
