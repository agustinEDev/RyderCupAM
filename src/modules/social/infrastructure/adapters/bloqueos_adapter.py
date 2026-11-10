"""Adaptador: los bloqueos que pregunta `user`, de las amistades de social."""

from src.modules.social.application.bloqueos import me_bloqueo
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.domain.value_objects.user_id import UserId


class BloqueosAdapter(BloqueosInterface):
    """Cada pregunta, una lectura de las amistades."""

    def __init__(self, social_uow: SocialUnitOfWorkInterface):
        """Con la unidad de trabajo de social."""
        self._social_uow = social_uow

    async def me_bloqueo(self, quien_mira: UserId, otro: UserId) -> bool:
        """Si `otro` bloqueó a `quien_mira`, con la regla de `Friendship.bloqueado_por`."""
        async with self._social_uow:
            return await me_bloqueo(self._social_uow.friendships, quien_mira, otro)

    async def quienes_me_bloquearon(self, quien_mira: UserId) -> frozenset[UserId]:
        """Los ids de quienes bloquearon a `quien_mira`, en una sola lectura."""
        async with self._social_uow:
            return frozenset(await self._social_uow.friendships.find_blocker_ids(quien_mira))
