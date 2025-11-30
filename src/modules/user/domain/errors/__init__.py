"""
User Domain Errors - Excepciones del dominio de usuarios

Exporta todas las excepciones específicas del dominio de usuarios,
incluyendo errores de validación, repositorio y operaciones de negocio.
"""

from .user_errors import (
    RepositoryConnectionError,
    RepositoryError,
    RepositoryOperationError,
    RepositoryTimeoutError,
    UserAlreadyExistsError,
    UserDomainError,
    UserNotFoundError,
    UserValidationError,
)

__all__ = [
    "RepositoryConnectionError",
    # Repository errors
    "RepositoryError",
    "RepositoryOperationError",
    "RepositoryTimeoutError",
    "UserAlreadyExistsError",
    # Base errors
    "UserDomainError",
    # Business logic errors
    "UserNotFoundError",
    # Validation errors
    "UserValidationError",
]
