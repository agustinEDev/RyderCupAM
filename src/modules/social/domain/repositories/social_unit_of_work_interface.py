"""
Social Unit of Work Interface - Social Module Domain Layer.

Define el contrato especifico para el Unit of Work del modulo Social (Friendship).
"""

from abc import abstractmethod

from src.shared.domain.repositories.unit_of_work_interface import UnitOfWorkInterface

from .friendship_repository_interface import FriendshipRepositoryInterface


class SocialUnitOfWorkInterface(UnitOfWorkInterface):
    """
    Interfaz especifica para el Unit of Work del modulo Social.

    Proporciona acceso coordinado al repositorio de amistades, manteniendo
    consistencia transaccional.
    """

    @property
    @abstractmethod
    def friendships(self) -> FriendshipRepositoryInterface:
        """Acceso al repositorio de amistades."""
        pass
