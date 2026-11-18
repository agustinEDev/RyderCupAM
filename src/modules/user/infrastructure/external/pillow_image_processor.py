"""
Pillow Image Processor - Infrastructure Layer Adapter

Implementación de IImageProcessor usando Pillow: valida, recorta a cuadrado,
redimensiona y comprime la imagen de avatar antes de guardarla en BD.

Pillow es síncrono y caro en memoria: cada imagen se procesa en el hilo de las
imágenes y de una en una en todo el proceso (`turno_de_imagenes`, SB-01).
"""

import io
import math
from collections.abc import Callable

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.errors.user_errors import InvalidAvatarImageError
from src.modules.user.infrastructure.external.turno_de_imagenes import en_su_turno

# Pillow no lee HEIC por su cuenta. Se registra al importar el módulo, una sola
# vez, para que `Image.open` lo reconozca igual que a los demás formatos.
register_heif_opener()

# Formatos de imagen de entrada aceptados (Pillow los normaliza todos a JPEG de salida).
# HEIF es el formato en el que un iPhone guarda las fotos de su fototeca: sin él, la
# única forma de poner avatar desde un iPhone era hacer una foto nueva, porque la
# cámara del navegador entrega JPEG y la fototeca entrega el HEIC original (BE #232).
# Ojo, Pillow lo identifica como "HEIF", no como "HEIC".
ALLOWED_INPUT_FORMATS = {"HEIF", "JPEG", "MPO", "PNG", "WEBP"}

# Los que son JPEG por dentro. Un JPEG de iPhone con mapa de ganancia HDR lleva dos
# imágenes y Pillow lo abre como «MPO», una subclase de su JPEG: mismo tope, misma
# decodificación reducida y sale la primera imagen, como de cualquier JPEG.
JPEG_FORMATS = {"JPEG", "MPO"}

# Dimensión final (cuadrada) del avatar
AVATAR_TARGET_SIZE = 512

# Lado mayor de las fotos de galeria. Medido con esta misma compresion: 512 px
# pesa 85 KB, 1080 px pesa 375 KB y 1600 px pesa 818 KB. 1600 casi triplica el
# peso de 1080 y en un telefono no se aprecia (BE #177).
GALLERY_MAX_SIDE = 1080

# Calidad de compresión JPEG de salida
AVATAR_JPEG_QUALITY = 85

# Topes de píxeles de la imagen de ENTRADA (protección contra "decompression
# bombs": un archivo de pocos KB puede declarar dimensiones absurdas y agotar
# memoria al decodificarse). Se miran en la cabecera, antes de decodificar nada.
#
# El JPEG se decodifica ya reducido al tamaño de salida (`Image.draft`, hasta 1/8
# por lado), así que su tope sube a 50 MP: entran las fotos de 48 MP de un iPhone
# (8064x6048). Medido: un JPEG progresivo de 48-50 MP sube ~150-170 MB, por
# debajo de los ~195 MB del peor PNG aceptado; y van de uno en uno (SB-01, 16 nov 2026).
MAX_JPEG_INPUT_PIXELS = 50_000_000
# El resto (PNG, HEIC, WEBP) se decodifica entero: unos 3 bytes por píxel y varias
# copias. 25 MP son las fotos de 24 MP de cámara (un iPhone de 24 MP guarda
# 5712x4284 = 24,47 MP), que tienen que seguir entrando (SB-01).
MAX_INPUT_PIXELS = 25_000_000


class PillowImageProcessor(IImageProcessor):
    """Procesa imágenes de avatar con Pillow: valida formato, crop centrado + resize + compresión."""

    async def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        return await en_su_turno(self._avatar, raw_bytes)

    async def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        """
        La misma validación que el avatar, pero sin recortar.

        Se conserva la proporción y se encaja el lado mayor en `GALLERY_MAX_SIDE`.
        Una foto que ya sea más pequeña se deja como está: ampliarla no añadiría
        detalle, solo peso.
        """
        return await en_su_turno(self._galeria, raw_bytes)

    def _avatar(self, raw_bytes: bytes) -> bytes:
        # El lado corto tiene que llegar a AVATAR_TARGET_SIZE: es el que da el cuadrado
        image = self._decode_and_validate(raw_bytes, lambda w, h: AVATAR_TARGET_SIZE / min(w, h))

        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        image = image.resize((AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE), Image.Resampling.LANCZOS)

        return self._to_jpeg(image)

    def _galeria(self, raw_bytes: bytes) -> bytes:
        # El lado largo tiene que llegar a GALLERY_MAX_SIDE
        image = self._decode_and_validate(raw_bytes, lambda w, h: GALLERY_MAX_SIDE / max(w, h))

        width, height = image.size
        lado_mayor = max(width, height)
        if lado_mayor > GALLERY_MAX_SIDE:
            escala = GALLERY_MAX_SIDE / lado_mayor
            nuevo = (max(1, round(width * escala)), max(1, round(height * escala)))
            image = image.resize(nuevo, Image.Resampling.LANCZOS)

        return self._to_jpeg(image)

    @staticmethod
    def _to_jpeg(image: Image.Image) -> bytes:
        # Sin nada de la foto original más que los píxeles (S-09): Pillow vuelve a
        # escribir el comentario, el EXIF o el perfil de color que queden en `info`, y
        # el comentario sobrevivía a la recodificación (cualquiera escondía ahí lo que
        # quisiera en una foto que se sirve a otros)
        image.info.clear()
        output = io.BytesIO()
        image.save(output, "JPEG", quality=AVATAR_JPEG_QUALITY, optimize=True)
        return output.getvalue()

    def _decode_and_validate(
        self, raw_bytes: bytes, escala_de_salida: Callable[[int, int], float]
    ) -> Image.Image:
        """
        Los pasos comunes a cualquier imagen que entre: comprobar que es una
        imagen de un formato admitido, que no es una bomba de descompresión, y
        dejarla en RGB con la orientación corregida.

        `escala_de_salida(ancho, alto)` dice a qué fracción se va a reducir la
        imagen: un JPEG se decodifica ya reducido hasta ahí, nunca por debajo.

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
        es_jpeg = probe_format in JPEG_FORMATS
        tope = MAX_JPEG_INPUT_PIXELS if es_jpeg else MAX_INPUT_PIXELS
        if width * height > tope:
            raise InvalidAvatarImageError(
                f"La imagen es demasiado grande ({width}x{height} píxeles)"
            )

        try:
            probe.verify()
            # Image.verify() deja el objeto inutilizable para operaciones posteriores;
            # hay que reabrirlo desde los mismos bytes para poder procesarlo de verdad.
            image: Image.Image = Image.open(io.BytesIO(raw_bytes))
            if es_jpeg:
                self._decodificar_reducido(image, escala_de_salida(width, height))
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise InvalidAvatarImageError("El archivo subido no es una imagen válida") from exc

        # Lo que de verdad se va a decodificar, ya con draft, no puede pasar del tope
        # de lo que se decodifica entero: un JPEG panorámico (50000x1000) para el
        # avatar no se reduce, porque manda su lado corto, y se decodificaría entero
        decodifica_ancho, decodifica_alto = image.size
        if decodifica_ancho * decodifica_alto > MAX_INPUT_PIXELS:
            raise InvalidAvatarImageError(
                f"La imagen es demasiado grande ({width}x{height} píxeles)"
            )

        # Corrige la orientación según el tag EXIF antes de nada más: si no, las
        # fotos tomadas en vertical con el móvil se guardarían giradas. Un HEIC
        # no pasa por aquí dos veces: pillow-heif ya lo entrega girado y con el
        # tag puesto a 1, así que `exif_transpose` lo deja como está.
        transposed = ImageOps.exif_transpose(image)
        if transposed is not None:
            image = transposed

        return image.convert("RGB")

    @staticmethod
    def _decodificar_reducido(image: Image.Image, escala: float) -> None:
        """
        Pide al decodificador del JPEG que lo entregue ya reducido (1/2, 1/4 o 1/8
        por lado), sin bajar del tamaño que necesita la salida: una foto de 48 MP
        para un avatar de 512 px se decodifica en ~0,8 MP en vez de en 48.
        La reducción fina la hace después el LANCZOS de siempre.
        """
        if escala >= 1:
            return
        width, height = image.size
        image.draft("RGB", (math.ceil(width * escala), math.ceil(height * escala)))
