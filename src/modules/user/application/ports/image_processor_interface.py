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

    @abstractmethod
    def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        """
        Valida y normaliza una imagen subida a la galería del perfil.

        Se diferencia del avatar en dos cosas, y por eso es un método aparte y no
        un parámetro de tamaño:

        - **No recorta a cuadrado.** Una foto de una vuelta de golf es casi
          siempre apaisada, y recortarla al centro se comería medio campo. Se
          conserva la proporción original y se encaja el lado mayor en el límite.
        - **Va a 1080 px** en vez de 512: estas fotos se miran, el avatar solo se
          reconoce.

        Args:
            raw_bytes: Bytes tal cual los subió el cliente (aún sin validar)

        Returns:
            bytes: Imagen ya procesada (JPEG)

        Raises:
            InvalidAvatarImageError: Si no es una imagen válida/soportada
        """
        pass
