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
