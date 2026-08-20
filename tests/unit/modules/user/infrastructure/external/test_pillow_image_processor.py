"""
Tests para PillowImageProcessor (procesado real con Pillow, sin mocks).
"""

import io

import pytest
from PIL import Image

from src.modules.user.domain.errors.user_errors import InvalidAvatarImageError
from src.modules.user.infrastructure.external.pillow_image_processor import (
    AVATAR_TARGET_SIZE,
    PillowImageProcessor,
)


def _make_test_image_bytes(width: int, height: int, fmt: str = "JPEG") -> bytes:
    image = Image.new("RGB", (width, height), color=(10, 200, 50))
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


class TestPillowImageProcessor:
    def test_processes_landscape_image_to_square_jpeg(self):
        processor = PillowImageProcessor()
        raw_bytes = _make_test_image_bytes(800, 400)

        result = processor.process_avatar_image(raw_bytes)

        output_image = Image.open(io.BytesIO(result))
        assert output_image.format == "JPEG"
        assert output_image.size == (AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE)

    def test_processes_portrait_png_to_square_jpeg(self):
        processor = PillowImageProcessor()
        raw_bytes = _make_test_image_bytes(300, 600, fmt="PNG")

        result = processor.process_avatar_image(raw_bytes)

        output_image = Image.open(io.BytesIO(result))
        assert output_image.format == "JPEG"
        assert output_image.size == (AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE)

    def test_rejects_non_image_bytes(self):
        processor = PillowImageProcessor()

        with pytest.raises(InvalidAvatarImageError):
            processor.process_avatar_image(b"this is definitely not an image")

    def test_rejects_unsupported_format(self):
        processor = PillowImageProcessor()
        image = Image.new("RGB", (100, 100))
        buffer = io.BytesIO()
        image.save(buffer, "BMP")

        with pytest.raises(InvalidAvatarImageError):
            processor.process_avatar_image(buffer.getvalue())

    def test_corrects_exif_orientation_before_cropping(self):
        """
        Una foto tomada en vertical con el móvil se guarda con los píxeles
        "en crudo" en una orientación y un tag EXIF que indica cómo rotarla
        para verse bien. Sin aplicar ese tag, el avatar saldría girado.
        """
        processor = PillowImageProcessor()
        image = Image.new("RGB", (400, 400))
        image.paste(Image.new("RGB", (400, 200), color=(255, 0, 0)), (0, 0))
        image.paste(Image.new("RGB", (400, 200), color=(0, 0, 255)), (0, 200))

        exif = image.getexif()
        exif[0x0112] = 3  # Orientation: rotar 180°

        buffer = io.BytesIO()
        image.save(buffer, "JPEG", exif=exif)

        result = processor.process_avatar_image(buffer.getvalue())

        output_image = Image.open(io.BytesIO(result)).convert("RGB")
        top_left = output_image.getpixel((5, 5))
        # Tras corregir una orientación de 180°, lo que era la mitad "azul"
        # (almacenada abajo) pasa a quedar arriba.
        assert top_left[2] > top_left[0]

    def test_rejects_image_exceeding_max_pixel_count(self, monkeypatch):
        """Protección contra 'decompression bombs': un archivo pequeño que
        declara dimensiones absurdas debe rechazarse antes de decodificarse."""
        import src.modules.user.infrastructure.external.pillow_image_processor as module

        monkeypatch.setattr(module, "MAX_INPUT_PIXELS", 100)
        processor = PillowImageProcessor()
        raw_bytes = _make_test_image_bytes(50, 50)  # 2500 px > 100 px (límite fingido)

        with pytest.raises(InvalidAvatarImageError):
            processor.process_avatar_image(raw_bytes)


class TestHeicFromAnIPhonePhotoLibrary:
    """
    Las fotos de la fototeca de un iPhone son HEIC (BE #232).

    Pillow no lo lee por su cuenta, así que la subida moría con «no es una
    imagen válida» y desde un iPhone solo se podía poner avatar haciendo una
    foto nueva: la cámara del navegador entrega JPEG y la fototeca entrega el
    HEIC original.
    """

    @staticmethod
    def _heic_bytes(width: int, height: int, exif: Image.Exif | None = None) -> bytes:
        image = Image.new("RGB", (width, height), color=(10, 200, 50))
        buffer = io.BytesIO()
        image.save(buffer, "HEIF", exif=exif.tobytes() if exif else None)
        return buffer.getvalue()

    def test_processes_a_heic_photo_to_square_jpeg(self):
        """
        Given una foto HEIC como las que guarda un iPhone
        When se procesa como avatar
        Then sale el mismo JPEG cuadrado que con cualquier otro formato
        """
        processor = PillowImageProcessor()

        result = processor.process_avatar_image(self._heic_bytes(800, 400))

        output_image = Image.open(io.BytesIO(result))
        assert output_image.format == "JPEG"
        assert output_image.size == (AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE)

    def test_processes_a_heic_photo_for_the_gallery(self):
        """La subida de foto de perfil comparte la validación, así que también entra."""
        processor = PillowImageProcessor()

        result = processor.process_gallery_image(self._heic_bytes(400, 300))

        assert Image.open(io.BytesIO(result)).format == "JPEG"

    def test_pillow_identifies_heic_as_heif(self):
        """
        El nombre del formato es lo que decide si se acepta, y Pillow llama
        «HEIF» a un HEIC. Poner «HEIC» en la lista no habría servido de nada.
        """
        assert Image.open(io.BytesIO(self._heic_bytes(60, 60))).format == "HEIF"

    def test_does_not_rotate_a_heic_twice(self):
        """
        pillow-heif ya entrega la imagen girada y con el tag EXIF a 1, así que
        `exif_transpose` no debe volver a girarla. Si alguna versión futura
        cambiara eso, las fotos verticales de iPhone saldrían tumbadas.
        """
        exif = Image.Exif()
        exif[274] = 6  # girar 90º
        raw = self._heic_bytes(400, 300, exif=exif)

        decoded = Image.open(io.BytesIO(raw))

        assert decoded.size == (300, 400), "pillow-heif debería entregarla ya girada"
        assert decoded.getexif().get(274) in (None, 1), "y con la orientación ya consumida"

    def test_still_rejects_a_format_that_is_not_allowed(self):
        """Aceptar HEIC no abre la puerta a cualquier cosa."""
        processor = PillowImageProcessor()
        buffer = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buffer, "BMP")

        with pytest.raises(InvalidAvatarImageError):
            processor.process_avatar_image(buffer.getvalue())

    def test_still_rejects_a_heic_over_the_pixel_limit(self, monkeypatch):
        """
        El tope de píxeles protege de una bomba de descompresión y tiene que
        seguir aplicando al formato nuevo, no solo a los de antes.
        """
        from src.modules.user.infrastructure.external import pillow_image_processor

        monkeypatch.setattr(pillow_image_processor, "MAX_INPUT_PIXELS", 100)
        processor = PillowImageProcessor()

        with pytest.raises(InvalidAvatarImageError, match="demasiado grande"):
            processor.process_avatar_image(self._heic_bytes(200, 200))

