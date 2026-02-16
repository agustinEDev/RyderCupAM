"""
OAuth Provider Value Object - Domain Layer

Enum que representa los proveedores OAuth soportados.
"""

from enum import StrEnum


class OAuthProvider(StrEnum):
    """
    Proveedores OAuth soportados por el sistema.

    Extensible para futuros proveedores (Apple, etc.).
    """

    GOOGLE = "google"
