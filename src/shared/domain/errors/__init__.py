"""
Shared Domain Errors - Excepciones compartidas entre módulos

Exporta las excepciones que pueden ser utilizadas por múltiples módulos del dominio.
"""

from .shared_domain_errors import (
    SharedDomainError,
    TransactionError,
    TransactionIsolationError,
    TransactionTimeoutError,
    UnitOfWorkCommitError,
    UnitOfWorkError,
    UnitOfWorkFlushError,
    UnitOfWorkRollbackError,
    UnitOfWorkStateError,
)

__all__ = [
    # Base errors
    "SharedDomainError",
    # Transaction errors
    "TransactionError",
    "TransactionIsolationError",
    "TransactionTimeoutError",
    "UnitOfWorkCommitError",
    # Unit of Work errors
    "UnitOfWorkError",
    "UnitOfWorkFlushError",
    "UnitOfWorkRollbackError",
    "UnitOfWorkStateError",
]
