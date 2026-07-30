"""
Image Processor Interface - Application Layer Port

Define el contrato para el procesado de imágenes subidas como avatar.
La capa de aplicación depende de esta abstracción, no de Pillow directamente.
"""

from abc import ABC, abstractmethod


class IImageProcessor(ABC):
    """
    Puerto para el procesado de imágenes de avatar.

    Implementaciones posibles:
    - PillowImageProcessor (producción, usa Pillow)
    - FakeImageProcessor (testing, evita dependencia de Pillow en tests unitarios)
    """

    @abstractmethod
    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        """
        Valida y normaliza una imagen subida para usarla como avatar.

        Debe: verificar que `raw_bytes` es una imagen decodificable en un formato
        soportado, recortarla a cuadrado (centrado), redimensionarla a un tamaño
        fijo y comprimirla a JPEG.

        Args:
            raw_bytes: Bytes tal cual los subió el cliente (aún sin validar)

        Returns:
            bytes: Imagen ya procesada (JPEG)

        Raises:
            InvalidAvatarImageError: Si no es una imagen válida/soportada
        """
        pass
