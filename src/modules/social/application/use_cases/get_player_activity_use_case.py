"""Caso de Uso: La actividad publicada por un jugador."""

from src.modules.social.application.dto.profile_dto import ActivityEventDTO, FeedResponseDTO
from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.application.feed_cursor import build_cursor, parse_cursor
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetPlayerActivityUseCase:
    """
    Los logros de un jugador concreto, visibles solo entre amigos.

    A diferencia del perfil —cuya ficha minima ve cualquiera—, la actividad es
    **solo para amigos**: es de lo que trata el componente social. Quien no lo
    sea recibe un 403 y no un 404, porque la existencia del jugador ya no es
    ningun secreto: acaba de poder ver su ficha.

    Y la misma regla de publicacion: con el interruptor apagado no hay actividad
    que enseñar, ni siquiera a un amigo.

    Reutiliza el paginado del feed en vez de repetirlo — es el mismo cursor
    sobre los mismos eventos, solo que de un autor en lugar de varios.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow

    async def execute(
        self,
        viewer_id_raw: str,
        target_id_raw: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> FeedResponseDTO:
        viewer_id = UserId(viewer_id_raw)
        target_id = UserId(target_id_raw)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        before, before_id = parse_cursor(cursor)

        async with self._user_uow:
            target = await self._user_uow.users.find_by_id(target_id)
            if target is None or not target.is_active:
                raise ProfileNotVisibleError("Profile not found")
            publica = target.share_activity

        if viewer_id != target_id:
            async with self._social_uow:
                if not await self._social_uow.friendships.are_friends(viewer_id, target_id):
                    raise ActivityNotVisibleError("Only friends can see this player's activity")

        # El interruptor apagado no es un error: el perfil existe y es visible,
        # simplemente no tiene actividad publicada.
        #
        # No se aplica a uno mismo. El interruptor gobierna lo que ven los demas,
        # no lo que uno ve de si mismo — es la misma regla que ya sigue el feed,
        # donde los logros propios salen tenga el interruptor como lo tenga.
        # Sin esta excepcion, apagarlo dejaria al jugador sin poder consultar su
        # propio historial.
        if not publica and viewer_id != target_id:
            return FeedResponseDTO()

        async with self._social_uow:
            eventos = await self._social_uow.activity_events.find_for_users(
                [target_id], limit=limit, before=before, before_id=before_id
            )

        return FeedResponseDTO(
            events=[
                ActivityEventDTO(
                    id=str(e.id),
                    user_id=str(e.user_id.value),
                    type=e.type.value,
                    occurred_at=e.occurred_at,
                    payload=e.payload,
                    source_match_id=e.source_match_id,
                )
                for e in eventos
            ],
            next_cursor=build_cursor(eventos, limit),
        )
