"""
Shared Domain Errors - Excepciones compartidas entre módulos

Exporta las excepciones que pueden ser utilizadas por múltiples módulos del dominio.
"""

from .shared_domain_errors import (
    SharedDomainError,
    TransactionError,
    UnitOfWorkError,
)

__all__ = [
    # Base errors
    "SharedDomainError",
    # Transaction errors
    "TransactionError",
    # Unit of Work errors
    "UnitOfWorkError",
]
