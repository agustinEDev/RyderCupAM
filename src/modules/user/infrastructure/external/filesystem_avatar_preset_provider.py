"""
FileSystem Avatar Preset Provider - Infrastructure Layer Adapter

Sirve las imágenes del catálogo fijo de presets de avatar desde los assets
estáticos empaquetados con el backend (src/modules/user/infrastructure/static/avatar_presets/).
"""

from pathlib import Path

from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.domain.entities.user import AVATAR_PRESET_COUNT
from src.modules.user.domain.errors.user_errors import InvalidAvatarPresetError

PRESETS_DIR = Path(__file__).parent.parent / "static" / "avatar_presets"


class FileSystemAvatarPresetProvider(IAvatarPresetProvider):
    """Lee los presets de avatar desde el sistema de ficheros (assets empaquetados)."""

    def get_preset_image(self, preset_id: int) -> tuple[bytes, str]:
        if not (1 <= preset_id <= AVATAR_PRESET_COUNT):
            raise InvalidAvatarPresetError(
                f"preset_id debe estar entre 1 y {AVATAR_PRESET_COUNT}, recibido: {preset_id}"
            )

        image_path = PRESETS_DIR / f"{preset_id}.jpg"
        if not image_path.is_file():
            raise InvalidAvatarPresetError(f"Asset de preset no encontrado: {image_path.name}")

        return image_path.read_bytes(), "image/jpeg"
