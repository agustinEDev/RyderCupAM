"""
Pillow Image Processor - Infrastructure Layer Adapter

Implementación de IImageProcessor usando Pillow: valida, recorta a cuadrado,
redimensiona y comprime la imagen de avatar antes de guardarla en BD.
"""

import io

from PIL import Image, UnidentifiedImageError

from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.errors.user_errors import InvalidAvatarImageError

# Formatos de imagen de entrada aceptados (Pillow los normaliza todos a JPEG de salida)
ALLOWED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP"}

# Dimensión final (cuadrada) del avatar
AVATAR_TARGET_SIZE = 512

# Calidad de compresión JPEG de salida
AVATAR_JPEG_QUALITY = 85


class PillowImageProcessor(IImageProcessor):
    """Procesa imágenes de avatar con Pillow: valida formato, crop centrado + resize + compresión."""

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        try:
            probe = Image.open(io.BytesIO(raw_bytes))
            probe.verify()
            # Image.verify() deja el objeto inutilizable para operaciones posteriores;
            # hay que reabrirlo desde los mismos bytes para poder procesarlo de verdad.
            image: Image.Image = Image.open(io.BytesIO(raw_bytes))
            image_format = image.format
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidAvatarImageError("El archivo subido no es una imagen válida") from exc

        if image_format not in ALLOWED_INPUT_FORMATS:
            raise InvalidAvatarImageError(
                f"Formato de imagen no soportado: {image_format}. "
                f"Formatos permitidos: {', '.join(sorted(ALLOWED_INPUT_FORMATS))}"
            )

        image = image.convert("RGB")
        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        image = image.resize((AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        image.save(output, "JPEG", quality=AVATAR_JPEG_QUALITY, optimize=True)
        return output.getvalue()
