"""
User Domain Errors - Excepciones del dominio de usuarios

Exporta todas las excepciones específicas del dominio de usuarios,
incluyendo errores de validación y operaciones de negocio.
"""

from .user_errors import (
    UserAlreadyExistsError,
    UserDomainError,
    UserNotFoundError,
)

__all__ = [
    "UserAlreadyExistsError",
    # Base errors
    "UserDomainError",
    # Business logic errors
    "UserNotFoundError",
]
