"""Caso de Uso: Eliminar una relacion de amistad (unfriend / cancelar / desbloquear)."""

from src.modules.social.application.exceptions import (
    FriendshipNotFoundError,
    NotFriendshipParticipantError,
)
from src.modules.social.domain.entities.friendship import Friendship
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
    - BLOCKED: desbloquear (solo quien realizo el bloqueo). Si se bloquearon los
      dos, solo se quita el suyo y el del otro sigue (SB-02)
    """

    def __init__(self, uow: SocialUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, friendship_id_raw: str, user_id_raw: str) -> None:
        friendship_id = FriendshipId(friendship_id_raw)
        user_id = UserId(user_id_raw)

        async with self._uow:
            # Con la fila bloqueada: un bloqueo del otro a la vez va antes o
            # después, nunca en medio (SB-02, caso 20)
            friendship = await self._uow.friendships.find_by_id_for_update(friendship_id)
            if not friendship:
                raise FriendshipNotFoundError(f"Friendship not found: {friendship_id}")

            if friendship.status == FriendshipStatus.PENDING:
                if friendship.requester_id != user_id:
                    raise NotFriendshipParticipantError(
                        "Only the requester can cancel a pending friend request."
                    )
            elif friendship.status == FriendshipStatus.BLOCKED:
                await self._desbloquea(friendship, user_id)
                return
            elif not friendship.involves_user(user_id):
                raise NotFriendshipParticipantError("You are not a participant of this friendship.")

            await self._uow.friendships.remove(friendship)

    async def _desbloquea(self, friendship: Friendship, user_id: UserId) -> None:
        """
        Quita su bloqueo. Al bloqueado que no bloqueó, el 404 de una fila que no
        existe: el 403 de antes («solo quien bloqueó…») le confirmaba el bloqueo
        (SB-02, caso 10). A un tercero, el 403 de no participar, como siempre.
        """
        if not friendship.bloqueado_por(user_id):
            if friendship.involves_user(user_id):
                raise FriendshipNotFoundError(f"Friendship not found: {friendship.id}")
            raise NotFriendshipParticipantError("You are not a participant of this friendship.")
        if friendship.unblock(user_id):
            await self._uow.friendships.remove(friendship)
        else:
            await self._uow.friendships.update(friendship)
