"""
Shared Domain Errors - Excepciones compartidas entre módulos

Define las excepciones que pueden ser utilizadas por múltiples módulos del dominio,
especialmente aquellas relacionadas con patrones como Unit of Work.
"""

from typing import Any


class SharedDomainError(Exception):
    """
    Excepción base para todos los errores del dominio compartido.

    Todas las excepciones específicas del dominio compartido deben heredar de esta clase.
    """

    def __init__(self, message: str, details: Any = None) -> None:
        self.message = message
        self.details = details
        super().__init__(self.message)


class UnitOfWorkError(SharedDomainError):
    """
    Excepción base para errores del patrón Unit of Work.

    Se utiliza para encapsular errores relacionados con la gestión de transacciones
    y coordinación entre repositorios.
    """
    pass


class UnitOfWorkCommitError(UnitOfWorkError):
    """
    Excepción lanzada cuando falla la operación commit del Unit of Work.

    Se utiliza cuando hay problemas al confirmar las operaciones pendientes,
    como violaciones de constraints, errores de conexión, etc.
    """
    pass


class UnitOfWorkRollbackError(UnitOfWorkError):
    """
    Excepción lanzada cuando falla la operación rollback del Unit of Work.

    Se utiliza cuando hay problemas al revertir las operaciones pendientes,
    situación crítica que puede requerir intervención manual.
    """
    pass


class UnitOfWorkFlushError(UnitOfWorkError):
    """
    Excepción lanzada cuando falla la operación flush del Unit of Work.

    Se utiliza cuando hay problemas al sincronizar el estado sin hacer commit,
    como violaciones de constraints o errores de validación.
    """
    pass


class UnitOfWorkStateError(UnitOfWorkError):
    """
    Excepción lanzada cuando el Unit of Work está en un estado inválido.

    Se utiliza cuando se intenta realizar operaciones en un UoW que no está
    activo o que ya ha sido finalizado.
    """
    pass


class TransactionError(SharedDomainError):
    """
    Excepción base para errores relacionados con transacciones.

    Se utiliza para encapsular errores generales de transacciones que pueden
    ocurrir en diferentes contextos, no solo en Unit of Work.
    """
    pass


class TransactionTimeoutError(TransactionError):
    """
    Excepción lanzada cuando una transacción excede el tiempo límite.

    Se utiliza cuando las operaciones de base de datos tardan más tiempo
    del configurado como límite máximo para transacciones.
    """
    pass


class TransactionIsolationError(TransactionError):
    """
    Excepción lanzada cuando hay problemas de aislamiento entre transacciones.

    Se utiliza cuando se detectan conflictos de concurrencia, deadlocks,
    o violaciones del nivel de aislamiento configurado.
    """
    pass
