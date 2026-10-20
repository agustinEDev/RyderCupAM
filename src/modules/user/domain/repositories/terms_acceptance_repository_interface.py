"""
Terms Acceptance Repository Interface - Domain Layer

Contrato del historial de aceptaciones de los Términos: solo se inserta y se lee.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from ..entities.terms_acceptance import TermsAcceptance
from ..value_objects.user_id import UserId


class TermsAcceptanceRepositoryInterface(ABC):
    """Historial de aceptaciones de los Términos: se inserta, se desvincula al borrar la cuenta y se purga."""

    @abstractmethod
    async def save(self, acceptance: TermsAcceptance) -> None:
        """Añade una aceptación al historial."""

    @abstractmethod
    async def has_accepted(self, user_id: UserId, terms_version: str) -> bool:
        """Si ese usuario ya tiene en el historial una fila de esa versión."""

    @abstractmethod
    async def find_by_user_id(self, user_id: UserId) -> list[TermsAcceptance]:
        """Las aceptaciones de un usuario, de la más antigua a la más reciente."""

    @abstractmethod
    async def detach_deleted_user(self, user_id: UserId, deleted_at: datetime) -> int:
        """
        La cuenta se borra: sus filas dejan de apuntarle y anotan cuándo.

        Va en la misma transacción que el borrado del usuario.

        Returns:
            Cuántas filas se han desvinculado
        """

    @abstractmethod
    async def purge_deleted_before(self, cutoff: datetime) -> int:
        """
        Borra las filas de cuentas borradas ANTES de `cutoff`.

        Returns:
            Cuántas filas se han borrado
        """
