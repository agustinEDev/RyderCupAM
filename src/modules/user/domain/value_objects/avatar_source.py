"""
Avatar Source Value Object - User Module Domain Layer
"""

from enum import StrEnum


class AvatarSource(StrEnum):
    """Origen del avatar activo de un usuario."""

    NONE = "NONE"
    PRESET = "PRESET"
    UPLOAD = "UPLOAD"

    def __str__(self) -> str:
        return self.value
