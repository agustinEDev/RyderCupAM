"""Caso de Uso: Las partidas que has jugado con un amigo («ver mas»)."""

from src.modules.social.application.dto.head_to_head_dto import GamesTogetherPageDTO
from src.modules.social.application.exceptions import (
    GamesTogetherNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.application.games_together import GAMES_PAGE_SIZE, page_of
from src.modules.social.application.ports.shared_games_interface import SharedGamesInterface
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetGamesTogetherUseCase:
    """
    Las partidas terminadas que jugaste con un amigo, de 5 en 5.

    Solo entre amigos, como la actividad: a cualquier otro, 403. De uno mismo
    no hay partidas juntos: una pagina vacia.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        shared_games: SharedGamesInterface,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._shared_games = shared_games

    async def execute(
        self,
        viewer_id_raw: str,
        target_id_raw: str,
        cursor: str | None = None,
        limit: int = GAMES_PAGE_SIZE,
    ) -> GamesTogetherPageDTO:
        """
        Raises:
            ProfileNotVisibleError: Si el jugador no existe o esta dado de baja (404)
            GamesTogetherNotVisibleError: Si no sois amigos (403)
        """
        viewer_id = UserId(viewer_id_raw)
        target_id = UserId(target_id_raw)

        async with self._user_uow:
            target = await self._user_uow.users.find_by_id(target_id)
            if target is None or not target.is_active:
                raise ProfileNotVisibleError("Profile not found")

        if viewer_id == target_id:
            return GamesTogetherPageDTO()

        async with self._social_uow:
            if not await self._social_uow.friendships.are_friends(viewer_id, target_id):
                raise GamesTogetherNotVisibleError(
                    "Only friends can see the games you played together"
                )

        juntos = await self._shared_games.between(viewer_id, target_id)
        return page_of(juntos, cursor, limit)
