"""Interfaz del repositorio de fotos de perfil."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from src.modules.social.domain.entities.profile_photo import ProfilePhoto
from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class ProfilePhotoMetadata:
    """
    Una foto **sin sus bytes**.

    Existe porque listar una galeria no necesita las imagenes: una galeria llena
    son mas de siete megas, y pintarlas es cosa de peticiones aparte que el
    navegador cachea. Traerlas para enseñar una lista de miniaturas seria mover
    esos megas en cada visita al perfil para tirarlos acto seguido.
    """

    id: ProfilePhotoId
    user_id: UserId
    caption: str | None
    created_at: datetime


class ProfilePhotoRepositoryInterface(ABC):
    """Acceso a las fotos de perfil."""

    @abstractmethod
    async def add(self, photo: ProfilePhoto) -> None:
        """Guarda una foto nueva."""

    @abstractmethod
    async def find_by_id(self, photo_id: ProfilePhotoId) -> ProfilePhoto | None:
        """La foto entera, con sus bytes. Es lo que se sirve al pedir la imagen."""

    @abstractmethod
    async def find_metadata_by_user(self, user_id: UserId) -> list[ProfilePhotoMetadata]:
        """
        La galeria de un jugador, de la mas reciente a la mas antigua y **sin
        los bytes de las imagenes**.
        """

    @abstractmethod
    async def count_by_user(self, user_id: UserId) -> int:
        """Cuantas fotos tiene ya. Lo consulta el tope por perfil."""

    @abstractmethod
    async def delete(self, photo_id: ProfilePhotoId) -> bool:
        """Borra una foto. Devuelve si existia."""
