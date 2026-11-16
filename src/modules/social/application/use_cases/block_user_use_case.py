"""Caso de Uso: Bloquear a un usuario."""

from src.modules.social.application.dto.friendship_dto import FriendshipResponseDTO
from src.modules.social.application.exceptions import AddresseeNotFoundError
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    DuplicateFriendshipViolation,
    InvalidFriendshipStatusViolation,
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


class BlockUserUseCase:
    """
    Bloquea a otro usuario.

    Si ya existia una relacion (PENDING/ACCEPTED), transiciona a BLOCKED.
    Si no existia ninguna relacion, crea directamente un registro BLOCKED.
    Operacion idempotente si ya estaba bloqueado.

    Si el otro ya le había bloqueado, se guardan los dos bloqueos (SB-02, 16 nov
    2026) y la respuesta es la de un bloqueo suyo: nada de la fila del otro (ni
    quién la puso ni cuándo) le dice que el otro le bloqueó antes.

    Residuo conocido: la fila conserva su id. Si guardaba el `friendship_id` de una
    amistad o solicitud que el otro convirtió en bloqueo, al bloquear recibe ese
    mismo id y podría deducir que la fila «sobrevivió» (aceptado en el diseño D1).
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
            # Con la fila bloqueada: un desbloqueo del otro a la vez va antes o
            # después, nunca en medio (SB-02, caso 20)
            friendship = await self._uow.friendships.find_by_pair_for_update(blocker_id, blocked_id)

            if friendship is None:
                friendship = Friendship.create_blocked(
                    id=FriendshipId.generate(),
                    blocker_id=blocker_id,
                    blocked_id=blocked_id,
                )
                try:
                    await self._uow.friendships.add(friendship)
                    await self._uow.flush()
                except DuplicateFriendshipViolation:
                    # Otra petición ganó la carrera del índice uq_friendship_pair (la
                    # traduce el adaptador de la UoW). Se relee lo que dejó. Si ya no
                    # está (la borró una tercera), es un conflicto: que lo intente de
                    # nuevo. Si es una solicitud o una amistad, se bloquea igualmente
                    ganadora = await self._uow.friendships.find_by_pair_for_update(
                        blocker_id, blocked_id
                    )
                    if ganadora is None:
                        raise InvalidFriendshipStatusViolation(
                            "The relationship changed while blocking; try again."
                        ) from None
                    friendship = ganadora
                    await self._bloquea(friendship, blocker_id)
            else:
                await self._bloquea(friendship, blocker_id)

        return await self._build_response(friendship, blocker_id)

    async def _bloquea(self, friendship: Friendship, blocker_id: UserId) -> None:
        """Su bloqueo sobre la fila que hay; si ya era suyo, no se toca (idempotente)."""
        if friendship.bloqueado_por(blocker_id):
            return
        friendship.block(blocker_id)
        await self._uow.friendships.update(friendship)

    async def _build_response(
        self, friendship: Friendship, blocker_id: UserId
    ) -> FriendshipResponseDTO:
        """
        La fila vista por quien bloquea. Si su bloqueo es el segundo (SB-02), la de un
        bloqueo suyo hecho de cero: él y el otro, y la hora de su bloqueo para todo.
        """
        requester_id, addressee_id = friendship.requester_id, friendship.addressee_id
        creada, actualizada, respondida = (
            friendship.created_at,
            friendship.updated_at,
            friendship.responded_at,
        )
        if friendship.segundo_bloqueador() == blocker_id and friendship.second_blocked_at:
            requester_id, addressee_id = blocker_id, friendship.other_user_id(blocker_id)
            creada = actualizada = respondida = friendship.second_blocked_at

        async with self._user_uow:
            requester = await self._user_uow.users.find_by_id(requester_id)
            addressee = await self._user_uow.users.find_by_id(addressee_id)
            # `display_name`: el alias de quien lo tenga, y si no su nombre
            # completo (BE #239). Estos dos campos son «nombre para enseñar»
            requester_name = requester.display_name if requester else "Unknown"
            addressee_name = addressee.display_name if addressee else "Unknown"

        return FriendshipResponseDTO(
            id=friendship.id.value,
            requester_id=requester_id.value,
            requester_name=requester_name,
            addressee_id=addressee_id.value,
            addressee_name=addressee_name,
            status=friendship.status.value,
            responded_at=respondida,
            created_at=creada,
            updated_at=actualizada,
        )
