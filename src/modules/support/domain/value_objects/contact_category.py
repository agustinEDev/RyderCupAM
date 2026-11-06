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
