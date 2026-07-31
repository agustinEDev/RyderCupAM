"""
List Avatar Presets Use Case - Application Layer

Lista el catálogo fijo de presets de avatar disponibles (1..AVATAR_PRESET_COUNT).
"""

from src.modules.user.application.dto.avatar_dto import AvatarPresetInfoDTO
from src.modules.user.domain.entities.user import AVATAR_PRESET_COUNT


class ListAvatarPresetsUseCase:
    """Caso de uso: listar los presets de avatar disponibles."""

    async def execute(self) -> list[AvatarPresetInfoDTO]:
        return [
            AvatarPresetInfoDTO(id=preset_id, image_url=f"/api/v1/avatar-presets/{preset_id}/image")
            for preset_id in range(1, AVATAR_PRESET_COUNT + 1)
        ]
