"""
Get Avatar Preset Image Use Case - Application Layer

Obtiene los bytes de la imagen de un preset concreto del catálogo fijo.
"""

from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)


class GetAvatarPresetImageUseCase:
    """Caso de uso: obtener los bytes de la imagen de un preset de avatar."""

    def __init__(self, preset_provider: IAvatarPresetProvider):
        self._preset_provider = preset_provider

    async def execute(self, preset_id: int) -> tuple[bytes, str]:
        return self._preset_provider.get_preset_image(preset_id)
