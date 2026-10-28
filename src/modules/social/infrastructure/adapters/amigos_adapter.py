"""Adaptador: los amigos que pregunta `competition`, de las amistades de social."""

from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class AmigosAdapter(AmigosInterface):
    """Una sola lectura de todos sus amigos aceptados (`find_friend_ids`)."""

    def __init__(self, social_uow: SocialUnitOfWorkInterface):
        self._social_uow = social_uow

    async def ids_de_los_amigos(self, user_id: UserId) -> frozenset[UserId]:
        """Sus amistades aceptadas, en una sola lectura."""
        async with self._social_uow:
            return frozenset(await self._social_uow.friendships.find_friend_ids(user_id))
