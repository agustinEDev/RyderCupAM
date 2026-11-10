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

from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
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
        bloqueos: BloqueosInterface,
    ):
        # Los bloqueos y quién mira, obligatorios: sin ellos no hay un «todos
        # pasan» por defecto que falle en abierto (revisión de la fase 3)
        """Con los usuarios, los presets y los bloqueos, obligatorios."""
        self._uow = uow
        self._preset_provider = preset_provider
        self._bloqueos = bloqueos

    async def execute(self, user_id: str, *, viewer_id: str) -> tuple[bytes, str]:
        """Los bytes del avatar; 404 si no existe, está de baja o su dueño bloqueó a quien mira."""
        user_id_vo = UserId(user_id)
        quien_mira = UserId(viewer_id)
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id_vo)
        if not user or not user.is_active:
            raise UserNotFoundError(f"User with id {user_id} not found")

        # Solo si es de otro y existe: una consulta, fuera de la unidad de trabajo de
        # usuarios (comparten sesión). El dueño y un id de nadie no la gastan
        if user.id != quien_mira and await self._bloqueos.me_bloqueo(quien_mira, user.id):
            raise UserNotFoundError(f"User with id {user_id} not found")

        if user.avatar_source == AvatarSource.NONE:
            raise AvatarNotFoundError(f"User {user_id} has no avatar set")

        if user.avatar_source == AvatarSource.PRESET:
            return self._preset_provider.get_preset_image(user.avatar_preset_id)

        # AvatarSource.UPLOAD
        async with self._uow:
            upload = await self._uow.avatar_uploads.find_by_id(user.active_avatar_upload_id)
        if not upload:
            raise AvatarNotFoundError(f"User {user_id} avatar upload no longer exists")

        return upload.image_data, upload.content_type
