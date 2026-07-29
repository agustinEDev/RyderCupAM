"""
Avatar Preset Provider Interface - Application Layer Port

Define el contrato para obtener las imágenes del catálogo fijo de presets de avatar
(las 10 fotos de golf empaquetadas con el backend).
"""

from abc import ABC, abstractmethod


class IAvatarPresetProvider(ABC):
    """
    Puerto para acceder a las imágenes de los presets de avatar.

    Implementaciones posibles:
    - FileSystemAvatarPresetProvider (producción, lee de disco los assets empaquetados)
    """

    @abstractmethod
    def get_preset_image(self, preset_id: int) -> tuple[bytes, str]:
        """
        Obtiene los bytes de la imagen de un preset.

        Args:
            preset_id: ID del preset (1..AVATAR_PRESET_COUNT)

        Returns:
            tuple[bytes, str]: (bytes de la imagen, content_type)

        Raises:
            InvalidAvatarPresetError: Si preset_id está fuera de rango o el asset no existe
        """
        pass
