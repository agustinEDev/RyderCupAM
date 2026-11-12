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


class TransactionError(SharedDomainError):
    """
    Excepción base para errores relacionados con transacciones.

    Se utiliza para encapsular errores generales de transacciones que pueden
    ocurrir en diferentes contextos, no solo en Unit of Work.
    """

    pass
