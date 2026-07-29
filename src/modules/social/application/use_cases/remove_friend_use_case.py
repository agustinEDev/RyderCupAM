"""Caso de Uso: Eliminar una relacion de amistad (unfriend / cancelar / desbloquear)."""

from src.modules.social.application.exceptions import (
    FriendshipNotFoundError,
    NotFriendshipParticipantError,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.user.domain.value_objects.user_id import UserId


class RemoveFriendUseCase:
    """
    Elimina definitivamente una relacion de amistad.

    Segun el estado actual, esta accion representa:
    - PENDING: cancelar una solicitud enviada (solo el requester)
    - ACCEPTED: eliminar una amistad (cualquiera de los dos participantes)
    - DECLINED: limpiar un registro terminal (cualquiera de los dos participantes)
    - BLOCKED: desbloquear (solo quien realizo el bloqueo)
    """

    def __init__(self, uow: SocialUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, friendship_id_raw: str, user_id_raw: str) -> None:
        friendship_id = FriendshipId(friendship_id_raw)
        user_id = UserId(user_id_raw)

        async with self._uow:
            friendship = await self._uow.friendships.find_by_id(friendship_id)
            if not friendship:
                raise FriendshipNotFoundError(f"Friendship not found: {friendship_id}")

            if friendship.status == FriendshipStatus.PENDING:
                if friendship.requester_id != user_id:
                    raise NotFriendshipParticipantError(
                        "Only the requester can cancel a pending friend request."
                    )
            elif friendship.status == FriendshipStatus.BLOCKED:
                if friendship.blocked_by != user_id:
                    raise NotFriendshipParticipantError(
                        "Only the user who blocked can remove this relationship."
                    )
            elif not friendship.involves_user(user_id):
                raise NotFriendshipParticipantError(
                    "You are not a participant of this friendship."
                )

            await self._uow.friendships.remove(friendship)
