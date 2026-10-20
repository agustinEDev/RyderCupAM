"""
Terms Acceptance Repository Interface - Domain Layer

Contrato del historial de aceptaciones de los Términos: solo se inserta y se lee.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from ..entities.terms_acceptance import TermsAcceptance
from ..value_objects.user_id import UserId


class TermsAcceptanceRepositoryInterface(ABC):
    """
    Historial de aceptaciones de los Términos: se inserta y se purga.

    Al borrar la cuenta, la base de datos desvincula sus filas (FK ON DELETE
    SET NULL) y anota cuándo (trigger BEFORE DELETE ON users): no hay método
    para eso, para que no dependa de que cada camino de borrado se acuerde.
    """

    @abstractmethod
    async def save(self, acceptance: TermsAcceptance) -> None:
        """Añade una aceptación al historial."""

    @abstractmethod
    async def has_accepted(self, user_id: UserId, terms_version: str) -> bool:
        """Si ese usuario ya tiene en el historial una fila de esa versión."""

    @abstractmethod
    async def purge_deleted_before(self, cutoff: datetime) -> int:
        """
        Borra las filas de cuentas borradas ANTES de `cutoff`.

        Returns:
            Cuántas filas se han borrado
        """
