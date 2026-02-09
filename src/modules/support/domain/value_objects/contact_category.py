"""
Contact Category Value Object

Categorías de contacto para el formulario de soporte.
"""

from enum import StrEnum


class ContactCategory(StrEnum):
    """Categorías disponibles para el formulario de contacto."""

    BUG = "BUG"
    FEATURE = "FEATURE"
    QUESTION = "QUESTION"
    OTHER = "OTHER"

    def to_github_label(self) -> str:
        """Mapea la categoría a un label de GitHub Issues."""
        label_map = {
            ContactCategory.BUG: "bug",
            ContactCategory.FEATURE: "enhancement",
            ContactCategory.QUESTION: "question",
            ContactCategory.OTHER: "other",
        }
        return label_map[self]
