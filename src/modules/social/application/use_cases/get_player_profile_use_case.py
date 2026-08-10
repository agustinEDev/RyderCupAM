"""Caso de Uso: Ver el perfil de un amigo."""

from src.modules.social.application.dto.profile_dto import PlayerProfileResponseDTO
from src.modules.social.application.exceptions import ProfileNotVisibleError
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetPlayerProfileUseCase:
    """
    El perfil de otro jugador, visible solo entre amigos.

    **La amistad es un guard, no un filtro.** Quien no es amigo no recibe una
    version recortada del perfil: no recibe perfil. La comprobacion decide si se
    responde, no cuanto se responde.

    Se comprueba en cada peticion y no se guarda nada en cache, que es lo que
    hace que deshacer una amistad retire el acceso al instante: la siguiente
    peticion ya no encuentra la relacion.

    El resumen de rendimiento sale de `GetPlayerStatsUseCase` tal cual. Ese caso
    de uso recibe un `UserId` cualquiera, asi que sirve para otro jugador sin
    tocar nada, y asi el perfil de un amigo enseña exactamente las mismas
    cifras que el propio panel en vez de una segunda version que se separaria
    con el tiempo.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        stats_use_case: GetPlayerStatsUseCase,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._stats = stats_use_case

    async def execute(self, viewer_id_raw: str, target_id_raw: str) -> PlayerProfileResponseDTO:
        """
        El perfil pedido, o `ProfileNotVisibleError` si no procede enseñarlo.

        Un jugador siempre puede verse a si mismo: sin esa salida, mirar el
        propio perfil exigiria ser amigo de uno mismo.
        """
        viewer_id = UserId(viewer_id_raw)
        target_id = UserId(target_id_raw)

        if viewer_id != target_id:
            async with self._social_uow:
                if not await self._social_uow.friendships.are_friends(viewer_id, target_id):
                    raise ProfileNotVisibleError("Profile not found")

        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(target_id)
            # La misma excepcion que para un desconocido: distinguir "no existe"
            # de "no sois amigos" convertiria esto en un detector de cuentas
            if user is None or not user.is_active:
                raise ProfileNotVisibleError("Profile not found")

            perfil = {
                "id": str(user.id.value),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "handicap": float(user.handicap.value) if user.handicap else None,
                "avatar_source": user.avatar_source.value,
                "avatar_preset_id": user.avatar_preset_id,
                "has_avatar_upload": user.active_avatar_upload_id is not None,
            }

        # Fuera de la unidad de trabajo: las estadisticas abren las suyas, y
        # anidarlas sobre la misma sesion la cerraria antes de tiempo
        stats = await self._stats.execute(target_id)

        return PlayerProfileResponseDTO(**perfil, stats=stats)
