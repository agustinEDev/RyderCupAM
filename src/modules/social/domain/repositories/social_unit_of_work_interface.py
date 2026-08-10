"""
Social Unit of Work Interface - Social Module Domain Layer.

Define el contrato especifico para el Unit of Work del modulo Social (Friendship).
"""

from abc import abstractmethod

from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface

from .activity_event_repository_interface import ActivityEventRepositoryInterface
from .friendship_repository_interface import FriendshipRepositoryInterface
from .profile_photo_repository_interface import ProfilePhotoRepositoryInterface


class SocialUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz especifica para el Unit of Work del modulo Social.

    Proporciona acceso coordinado a los repositorios de amistades y de eventos
    de actividad, manteniendo consistencia transaccional.
    """

    @property
    @abstractmethod
    def friendships(self) -> FriendshipRepositoryInterface:
        """Acceso al repositorio de amistades."""
        pass

    @property
    @abstractmethod
    def activity_events(self) -> ActivityEventRepositoryInterface:
        """Acceso al repositorio de eventos de actividad."""
        pass

    @property
    @abstractmethod
    def profile_photos(self) -> ProfilePhotoRepositoryInterface:
        """Acceso al repositorio de fotos de perfil."""
        pass
