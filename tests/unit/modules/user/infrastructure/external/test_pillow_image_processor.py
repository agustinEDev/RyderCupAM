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
