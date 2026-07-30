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

# Whitelist explícita id -> nombre de fichero literal. No se construye el nombre
# interpolando preset_id en un string: así el path nunca depende de un valor
# derivado del input (evita el aviso de CodeQL "uncontrolled data in path
# expression", aunque preset_id ya viniera tipado como int y validado por rango).
_PRESET_FILENAMES: dict[int, str] = {i: f"{i}.jpg" for i in range(1, AVATAR_PRESET_COUNT + 1)}


class FileSystemAvatarPresetProvider(IAvatarPresetProvider):
    """Lee los presets de avatar desde el sistema de ficheros (assets empaquetados)."""

    def get_preset_image(self, preset_id: int) -> tuple[bytes, str]:
        filename = _PRESET_FILENAMES.get(preset_id)
        if filename is None:
            raise InvalidAvatarPresetError(
                f"preset_id debe estar entre 1 y {AVATAR_PRESET_COUNT}, recibido: {preset_id}"
            )

        image_path = PRESETS_DIR / filename
        if not image_path.is_file():
            raise InvalidAvatarPresetError(f"Asset de preset no encontrado: {image_path.name}")

        return image_path.read_bytes(), "image/jpeg"
