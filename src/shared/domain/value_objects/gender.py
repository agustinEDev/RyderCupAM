"""
Gender Value Object — Shared between User and Golf Course modules.
"""

from enum import StrEnum


class Gender(StrEnum):
    """Género biológico para selección de tees y categorización de jugadores."""

    MALE = "MALE"
    FEMALE = "FEMALE"

    def __str__(self) -> str:
        return self.value
