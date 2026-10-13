"""Caso de Uso: Listar los amigos (ACCEPTED) de un usuario."""

from src.modules.social.application.dto.friendship_dto import (
    FriendResponseDTO,
    PaginatedFriendResponseDTO,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class ListFriendsUseCase:
    """Lista las amistades aceptadas del usuario autenticado."""

    def __init__(
        self,
        uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self, user_id_raw: str, page: int = 1, limit: int = 20
    ) -> PaginatedFriendResponseDTO:
        user_id = UserId(user_id_raw)
        offset = (page - 1) * limit

        async with self._uow:
            friendships = await self._uow.friendships.list_friends(
                user_id, limit=limit, offset=offset
            )
            total_count = await self._uow.friendships.count_friends(user_id)

        # Todos los usuarios en una consulta, no dos por amistad
        user_ids = list({uid for f in friendships for uid in (f.requester_id, f.addressee_id)})
        async with self._user_uow:
            users = await self._user_uow.users.find_by_ids(user_ids) if user_ids else []
        by_id = {user.id: user for user in users if user.id is not None}

        items = [self._to_dto(f, by_id) for f in friendships]

        return PaginatedFriendResponseDTO(
            friendships=items,
            total_count=total_count,
            page=page,
            limit=limit,
        )

    @staticmethod
    def _to_dto(friendship: Friendship, by_id: dict[UserId, User]) -> FriendResponseDTO:
        requester = by_id.get(friendship.requester_id)
        addressee = by_id.get(friendship.addressee_id)

        def handicap(user: User | None) -> float | None:
            return user.handicap.value if user and user.handicap else None

        return FriendResponseDTO(
            id=friendship.id.value,
            requester_id=friendship.requester_id.value,
            # `display_name`: el alias de quien lo tenga, y si no su nombre
            # completo (BE #239). Estos dos campos son «nombre para enseñar»
            requester_name=requester.display_name if requester else "Unknown",
            addressee_id=friendship.addressee_id.value,
            addressee_name=addressee.display_name if addressee else "Unknown",
            status=friendship.status.value,
            responded_at=friendship.responded_at,
            created_at=friendship.created_at,
            updated_at=friendship.updated_at,
            requester_handicap=handicap(requester),
            addressee_handicap=handicap(addressee),
        )
