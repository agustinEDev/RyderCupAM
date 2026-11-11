"""
Get Avatar Image Use Case - Application Layer

Obtiene los bytes de la imagen del avatar ACTIVO de un usuario cualquiera
(propio o de otro usuario) — resuelve internamente si toca leer un preset
(disco) o una foto subida (BD), para que el frontend pueda mostrar el avatar
de cualquier usuario con una única URL, sin conocer el origen.

Devuelve la imagen o `None`, sin excepciones para el camino normal (2.59.0, BE #793):
sin avatar, un usuario inexistente o desactivado, alguien que bloqueó a quien lo pide
(F-09, opción A de Agustín, 10 nov 2026) y una foto activa que ya no está son el mismo
«no hay imagen», y la ruta responde a todos el mismo 204 (código, cabeceras y cuerpo).
Por tiempo, «sin avatar» y «me bloqueó» hacen el mismo trabajo (una consulta de
bloqueos); solo «no existe» se ahorra esa consulta, y eso dice que una cuenta existe,
nunca un bloqueo. Quien bloqueó sí ve el del bloqueado: su perfil le enseña nombre y
foto para poder desbloquearlo.
"""

from src.modules.user.application.dto.avatar_dto import ImagenDeAvatar
from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.domain.entities.user import User
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

    async def execute(self, user_id: str, *, viewer_id: str) -> ImagenDeAvatar | None:
        """La imagen del avatar, o None si no hay ninguna que enseñar a quien mira."""
        user_id_vo = UserId(user_id)
        quien_mira = UserId(viewer_id)
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id_vo)
        if not user or not user.is_active:
            return None

        # Solo si es de otro y existe: una consulta, fuera de la unidad de trabajo de
        # usuarios (comparten sesión). El dueño y un id de nadie no la gastan. Se pregunta
        # también si no tiene avatar: sin avatar y bloqueado hacen el mismo trabajo
        if user.id != quien_mira and await self._bloqueos.me_bloqueo(quien_mira, user.id):
            return None

        return await self._imagen_de(user)

    async def _imagen_de(self, user: User) -> ImagenDeAvatar | None:
        """La imagen activa del usuario, o None si no tiene ninguna."""
        if user.avatar_source == AvatarSource.NONE:
            return None

        if user.avatar_source == AvatarSource.PRESET:
            # Sin id de cuál, un dato roto: sin imagen, como la foto borrada (antes, un 500).
            # Un fichero de preset que falte sí sale como error: es del despliegue
            if user.avatar_preset_id is None:
                return None
            datos, tipo = self._preset_provider.get_preset_image(user.avatar_preset_id)
            return ImagenDeAvatar(datos=datos, tipo=tipo)

        # AvatarSource.UPLOAD. Sin id, la foto se borró y la base de datos lo dejó a NULL
        # (ON DELETE SET NULL): no hay a qué buscar (antes, un 500)
        if user.active_avatar_upload_id is None:
            return None
        async with self._uow:
            upload = await self._uow.avatar_uploads.find_by_id(user.active_avatar_upload_id)
        if not upload:
            return None

        return ImagenDeAvatar(datos=upload.image_data, tipo=upload.content_type)
