"""
Friendship Repository Interface - Domain Layer.

Define el contrato para la persistencia de amistades siguiendo Clean Architecture.
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.friendship import Friendship
from ..value_objects.friendship_id import FriendshipId


class FriendshipRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de amistades.

    Define las operaciones CRUD y consultas especificas del dominio Social.
    """

    @abstractmethod
    async def add(self, friendship: Friendship) -> None:
        """Agrega una nueva relacion de amistad al repositorio."""
        pass

    @abstractmethod
    async def update(self, friendship: Friendship) -> None:
        """Actualiza una relacion de amistad existente en el repositorio."""
        pass

    @abstractmethod
    async def remove(self, friendship: Friendship) -> None:
        """Elimina definitivamente una relacion de amistad (unfriend / unblock)."""
        pass

    @abstractmethod
    async def find_by_id(self, friendship_id: FriendshipId) -> Friendship | None:
        """Busca una relacion de amistad por su ID unico."""
        pass

    @abstractmethod
    async def find_by_pair(self, user_id_a: UserId, user_id_b: UserId) -> Friendship | None:
        """
        Busca la relacion de amistad (en cualquier estado) entre dos usuarios,
        independientemente de quien sea requester/addressee.
        """
        pass

    @abstractmethod
    async def list_friends(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        """Lista las relaciones ACCEPTED en las que participa el usuario."""
        pass

    @abstractmethod
    async def list_pending_received(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        """Lista las solicitudes PENDING recibidas por el usuario (es el addressee)."""
        pass

    @abstractmethod
    async def list_pending_sent(
        self, user_id: UserId, limit: int = 20, offset: int = 0
    ) -> list[Friendship]:
        """Lista las solicitudes PENDING enviadas por el usuario (es el requester)."""
        pass

    @abstractmethod
    async def count_friends(self, user_id: UserId) -> int:
        """Cuenta las relaciones ACCEPTED en las que participa el usuario."""
        pass

    @abstractmethod
    async def count_pending_received(self, user_id: UserId) -> int:
        """Cuenta las solicitudes PENDING recibidas por el usuario."""
        pass

    @abstractmethod
    async def count_pending_sent(self, user_id: UserId) -> int:
        """Cuenta las solicitudes PENDING enviadas por el usuario."""
        pass

    @abstractmethod
    async def are_friends(self, user_id_a: UserId, user_id_b: UserId) -> bool:
        """Verifica si dos usuarios tienen una amistad en estado ACCEPTED."""
        pass
