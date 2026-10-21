"""Caso de Uso: Cuantas novedades hay en mi feed."""

from collections.abc import Callable
from datetime import datetime

from src.modules.social.application.dto.profile_dto import FeedUnseenCountResponseDTO
from src.modules.social.application.feed_scope import count_unseen, resolve_feed_scope
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.utc_clock import utc_now


class GetFeedUnseenCountUseCase:
    """
    El numero del boton de Actividad, sin cargar el feed.

    El cliente lo pide al abrir la app y al volver a ella, asi que tiene que
    ser barato: ni eventos, ni autores, ni campos; solo un recuento con tope.
    Sale de la misma regla que el `unseen_count` del feed, para que el boton y
    la pantalla no discrepen.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        reloj: Callable[[], datetime] = utc_now,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._reloj = reloj

    async def execute(self, viewer_id_raw: str) -> FeedUnseenCountResponseDTO:
        scope = await resolve_feed_scope(
            self._social_uow, self._user_uow, UserId(viewer_id_raw), self._reloj
        )
        async with self._social_uow:
            no_vistos = await count_unseen(self._social_uow.activity_events, scope)
        return FeedUnseenCountResponseDTO(unseen_count=no_vistos)
