"""
User Avatar Upload Repository Interface - Domain Layer

Define el contrato para la persistencia de fotos de avatar subidas por usuarios.
"""

from abc import ABC, abstractmethod

from ..entities.user_avatar_upload import UserAvatarUpload
from ..value_objects.user_avatar_upload_id import UserAvatarUploadId
from ..value_objects.user_id import UserId


class UserAvatarUploadRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de fotos de avatar subidas.

    El historial por usuario está acotado (AVATAR_MAX_STORED_UPLOADS, ver user.py):
    el caso de uso de subida es responsable de podar (FIFO) las más antiguas
    tras guardar una nueva, usando `find_by_user` + `delete`.
    """

    @abstractmethod
    async def save(self, upload: UserAvatarUpload) -> None:
        """Guarda una nueva foto de avatar subida."""
        pass

    @abstractmethod
    async def find_by_id(self, upload_id: UserAvatarUploadId) -> UserAvatarUpload | None:
        """Busca una foto subida por su id. None si no existe."""
        pass

    @abstractmethod
    async def find_by_user(self, user_id: UserId) -> list[UserAvatarUpload]:
        """
        Lista las fotos subidas por un usuario, ordenadas por created_at DESC
        (más reciente primero).
        """
        pass

    @abstractmethod
    async def count_by_user(self, user_id: UserId) -> int:
        """Cuenta cuántas fotos tiene subidas un usuario."""
        pass

    @abstractmethod
    async def delete(self, upload_id: UserAvatarUploadId) -> None:
        """Elimina una foto subida por su id."""
        pass
