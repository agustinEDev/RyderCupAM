"""
User Domain Errors - Excepciones del dominio de usuarios

Exporta todas las excepciones específicas del dominio de usuarios,
incluyendo errores de validación, repositorio y operaciones de negocio.
"""

from .user_errors import (
    UserDomainError,
    UserValidationError,
    UserNotFoundError,
    UserAlreadyExistsError,
    RepositoryError,
    RepositoryConnectionError,
    RepositoryOperationError,
    RepositoryTimeoutError,
)

__all__ = [
    # Base errors
    "UserDomainError",
    
    # Validation errors
    "UserValidationError",
    
    # Business logic errors
    "UserNotFoundError",
    "UserAlreadyExistsError",
    
    # Repository errors
    "RepositoryError",
    "RepositoryConnectionError",
    "RepositoryOperationError",
    "RepositoryTimeoutError",
]