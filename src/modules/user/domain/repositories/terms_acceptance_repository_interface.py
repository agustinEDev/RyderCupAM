"""
Terms Acceptance Repository Interface - Domain Layer

Contrato del historial de aceptaciones de los Términos: solo se inserta y se lee.
"""

from abc import ABC, abstractmethod

from ..entities.terms_acceptance import TermsAcceptance
from ..value_objects.user_id import UserId


class TermsAcceptanceRepositoryInterface(ABC):
    """Historial de aceptaciones de los Términos. Sin actualizar ni borrar filas."""

    @abstractmethod
    async def save(self, acceptance: TermsAcceptance) -> None:
        """Añade una aceptación al historial."""

    @abstractmethod
    async def find_by_user_id(self, user_id: UserId) -> list[TermsAcceptance]:
        """Las aceptaciones de un usuario, de la más antigua a la más reciente."""
