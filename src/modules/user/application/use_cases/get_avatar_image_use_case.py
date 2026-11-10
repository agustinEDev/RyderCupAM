"""
Get Avatar Image Use Case - Application Layer

Obtiene los bytes de la imagen del avatar ACTIVO de un usuario cualquiera
(propio o de otro usuario) — resuelve internamente si toca leer un preset
(disco) o una foto subida (BD), para que el frontend pueda mostrar el avatar
de cualquier usuario con una única URL, sin conocer el origen.

El de una cuenta desactivada, o el de alguien que bloqueó a quien lo pide, no
existe para él: el mismo 404 que un usuario inexistente (F-09, fase 3 del plan a
9, opción A de Agustín, 10 nov 2026). Quien bloqueó sí ve el del bloqueado: su
perfil le enseña nombre y foto para poder desbloquearlo.
"""

from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.domain.errors.user_errors import AvatarNotFoundError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
from src.modules.user.domain.value_objects.user_id import UserId


class GetAvatarImageUseCase:
    """Caso de uso: obtener los bytes del avatar activo de un usuario."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        preset_provider: IAvatarPresetProvider,
        social_uow: SocialUnitOfWorkInterface | None = None,
    ):
        self._uow = uow
        self._preset_provider = preset_provider
        self._social_uow = social_uow

    async def execute(self, user_id: str, viewer_id: str | None = None) -> tuple[bytes, str]:
        user_id_vo = UserId(user_id)
        # Antes de leer el avatar, y en su propia unidad de trabajo: comparten sesión
        if viewer_id is not None and await self._me_bloqueo(user_id_vo, UserId(viewer_id)):
            raise UserNotFoundError(f"User with id {user_id} not found")

        async with self._uow:
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user or not user.is_active:
                raise UserNotFoundError(f"User with id {user_id} not found")

            if user.avatar_source == AvatarSource.NONE:
                raise AvatarNotFoundError(f"User {user_id} has no avatar set")

            if user.avatar_source == AvatarSource.PRESET:
                return self._preset_provider.get_preset_image(user.avatar_preset_id)

            # AvatarSource.UPLOAD
            upload = await self._uow.avatar_uploads.find_by_id(user.active_avatar_upload_id)
            if not upload:
                raise AvatarNotFoundError(f"User {user_id} avatar upload no longer exists")

            return upload.image_data, upload.content_type

    async def _me_bloqueo(self, dueno: UserId, quien_mira: UserId) -> bool:
        """Si el dueño del avatar bloqueó a quien lo pide (no al revés)."""
        if self._social_uow is None or dueno == quien_mira:
            return False
        async with self._social_uow:
            relacion = await self._social_uow.friendships.find_by_pair(dueno, quien_mira)
        return relacion is not None and relacion.is_blocked() and relacion.blocked_by == dueno
