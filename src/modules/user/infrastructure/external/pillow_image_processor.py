"""
Pillow Image Processor - Infrastructure Layer Adapter

Implementación de IImageProcessor usando Pillow: valida, recorta a cuadrado,
redimensiona y comprime la imagen de avatar antes de guardarla en BD.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.errors.user_errors import InvalidAvatarImageError

# Pillow no lee HEIC por su cuenta. Se registra al importar el módulo, una sola
# vez, para que `Image.open` lo reconozca igual que a los demás formatos.
register_heif_opener()

# Formatos de imagen de entrada aceptados (Pillow los normaliza todos a JPEG de salida).
# HEIF es el formato en el que un iPhone guarda las fotos de su fototeca: sin él, la
# única forma de poner avatar desde un iPhone era hacer una foto nueva, porque la
# cámara del navegador entrega JPEG y la fototeca entrega el HEIC original (BE #232).
# Ojo, Pillow lo identifica como "HEIF", no como "HEIC".
ALLOWED_INPUT_FORMATS = {"HEIF", "JPEG", "PNG", "WEBP"}

# Dimensión final (cuadrada) del avatar
AVATAR_TARGET_SIZE = 512

# Lado mayor de las fotos de galeria. Medido con esta misma compresion: 512 px
# pesa 85 KB, 1080 px pesa 375 KB y 1600 px pesa 818 KB. 1600 casi triplica el
# peso de 1080 y en un telefono no se aprecia (BE #177).
GALLERY_MAX_SIDE = 1080

# Calidad de compresión JPEG de salida
AVATAR_JPEG_QUALITY = 85

# Tope de píxeles de la imagen de ENTRADA (protección contra "decompression
# bombs": un archivo de pocos KB puede declarar dimensiones absurdas y agotar
# memoria al decodificarse). 40MP cubre con margen cualquier foto de móvil real.
MAX_INPUT_PIXELS = 40_000_000


class PillowImageProcessor(IImageProcessor):
    """Procesa imágenes de avatar con Pillow: valida formato, crop centrado + resize + compresión."""

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        image = self._decode_and_validate(raw_bytes)

        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        image = image.resize((AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE), Image.Resampling.LANCZOS)

        return self._to_jpeg(image)

    def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        """
        La misma validación que el avatar, pero sin recortar.

        Se conserva la proporción y se encaja el lado mayor en `GALLERY_MAX_SIDE`.
        Una foto que ya sea más pequeña se deja como está: ampliarla no añadiría
        detalle, solo peso.
        """
        image = self._decode_and_validate(raw_bytes)

        width, height = image.size
        lado_mayor = max(width, height)
        if lado_mayor > GALLERY_MAX_SIDE:
            escala = GALLERY_MAX_SIDE / lado_mayor
            nuevo = (max(1, round(width * escala)), max(1, round(height * escala)))
            image = image.resize(nuevo, Image.Resampling.LANCZOS)

        return self._to_jpeg(image)

    @staticmethod
    def _to_jpeg(image: Image.Image) -> bytes:
        output = io.BytesIO()
        image.save(output, "JPEG", quality=AVATAR_JPEG_QUALITY, optimize=True)
        return output.getvalue()

    def _decode_and_validate(self, raw_bytes: bytes) -> Image.Image:
        """
        Los pasos comunes a cualquier imagen que entre: comprobar que es una
        imagen de un formato admitido, que no es una bomba de descompresión, y
        dejarla en RGB con la orientación corregida.

        Es compartido a proposito: la validacion es lo unico que protege al
        servidor de lo que suba un cliente, y dos copias se separarian.
        """
        try:
            probe = Image.open(io.BytesIO(raw_bytes))
            probe_format = probe.format
            width, height = probe.size
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ) as exc:
            raise InvalidAvatarImageError("El archivo subido no es una imagen válida") from exc

        if probe_format not in ALLOWED_INPUT_FORMATS:
            raise InvalidAvatarImageError(
                f"Formato de imagen no soportado: {probe_format}. "
                f"Formatos permitidos: {', '.join(sorted(ALLOWED_INPUT_FORMATS))}"
            )

        # Comprobar el tope de píxeles ANTES de decodificar nada (Image.open()
        # solo lee la cabecera; .size no fuerza la decodificación completa).
        if width * height > MAX_INPUT_PIXELS:
            raise InvalidAvatarImageError(
                f"La imagen es demasiado grande ({width}x{height} píxeles)"
            )

        try:
            probe.verify()
            # Image.verify() deja el objeto inutilizable para operaciones posteriores;
            # hay que reabrirlo desde los mismos bytes para poder procesarlo de verdad.
            image: Image.Image = Image.open(io.BytesIO(raw_bytes))
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise InvalidAvatarImageError("El archivo subido no es una imagen válida") from exc

        # Corrige la orientación según el tag EXIF antes de nada más: si no, las
        # fotos tomadas en vertical con el móvil se guardarían giradas. Un HEIC
        # no pasa por aquí dos veces: pillow-heif ya lo entrega girado y con el
        # tag puesto a 1, así que `exif_transpose` lo deja como está.
        transposed = ImageOps.exif_transpose(image)
        if transposed is not None:
            image = transposed

        return image.convert("RGB")
