"""
Shared Domain Errors - Excepciones compartidas entre módulos

Exporta las excepciones que pueden ser utilizadas por múltiples módulos del dominio.
"""

from .shared_domain_errors import (
    SharedDomainError,
    UnitOfWorkError,
    UnitOfWorkCommitError,
    UnitOfWorkRollbackError,
    UnitOfWorkFlushError,
    UnitOfWorkStateError,
    TransactionError,
    TransactionTimeoutError,
    TransactionIsolationError,
)

__all__ = [
    # Base errors
    "SharedDomainError",
    
    # Unit of Work errors
    "UnitOfWorkError",
    "UnitOfWorkCommitError",
    "UnitOfWorkRollbackError",
    "UnitOfWorkFlushError",
    "UnitOfWorkStateError",
    
    # Transaction errors
    "TransactionError",
    "TransactionTimeoutError",
    "TransactionIsolationError",
]