"""
User Domain Errors - Excepciones del dominio de usuarios

Exporta todas las excepciones específicas del dominio de usuarios,
incluyendo errores de validación, repositorio y operaciones de negocio.
"""

from .user_errors import (
    RepositoryError,
    UserAlreadyExistsError,
    UserDomainError,
    UserNotFoundError,
)

__all__ = [
    # Repository errors
    "RepositoryError",
    "UserAlreadyExistsError",
    # Base errors
    "UserDomainError",
    # Business logic errors
    "UserNotFoundError",
]
