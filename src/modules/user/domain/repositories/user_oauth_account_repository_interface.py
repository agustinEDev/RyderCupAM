"""
User OAuth Account Repository Interface - Domain Layer

Define el contrato para la persistencia de cuentas OAuth vinculadas.
"""

from abc import ABC, abstractmethod

from ..entities.user_oauth_account import UserOAuthAccount
from ..value_objects.oauth_provider import OAuthProvider
from ..value_objects.user_id import UserId


class UserOAuthAccountRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de cuentas OAuth.

    Define las operaciones necesarias para gestionar la vinculación
    de cuentas OAuth (Google, etc.) con usuarios del sistema.
    """

    @abstractmethod
    async def save(self, oauth_account: UserOAuthAccount) -> None:
        """Persiste una cuenta OAuth."""
        pass

    @abstractmethod
    async def find_by_provider_and_provider_user_id(
        self, provider: OAuthProvider, provider_user_id: str
    ) -> UserOAuthAccount | None:
        """Busca una cuenta OAuth por proveedor e ID del proveedor."""
        pass

    @abstractmethod
    async def find_by_user_id(self, user_id: UserId) -> list[UserOAuthAccount]:
        """Obtiene todas las cuentas OAuth de un usuario."""
        pass

    @abstractmethod
    async def find_by_user_id_and_provider(
        self, user_id: UserId, provider: OAuthProvider
    ) -> UserOAuthAccount | None:
        """Busca una cuenta OAuth por usuario y proveedor."""
        pass

    @abstractmethod
    async def delete(self, oauth_account: UserOAuthAccount) -> None:
        """Elimina una cuenta OAuth."""
        pass
