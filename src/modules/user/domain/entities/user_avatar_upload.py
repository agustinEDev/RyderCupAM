"""
User Avatar Upload Entity - Domain Layer

Representa una foto de avatar subida por un usuario. Se conserva un historial
acotado por usuario (ver AVATAR_MAX_STORED_UPLOADS en user.py) para poder alternar
entre fotos ya subidas sin tener que volver a subirlas.
"""

from datetime import datetime

from ..value_objects.user_avatar_upload_id import UserAvatarUploadId
from ..value_objects.user_id import UserId


class UserAvatarUpload:
    """
    Entidad UserAvatarUpload - Una foto de avatar subida por un usuario.

    Attributes:
        id (UserAvatarUploadId): Identificador único de la foto subida
        user_id (UserId): Referencia al usuario dueño de la foto
        image_data (bytes): Bytes de la imagen ya redimensionada/comprimida (JPEG)
        content_type (str): Content-Type de la imagen (siempre "image/jpeg" tras procesado)
        created_at (datetime): Timestamp de cuándo se subió
    """

    def __init__(
        self,
        id: UserAvatarUploadId | None,
        user_id: UserId,
        image_data: bytes,
        content_type: str,
        created_at: datetime | None = None,
    ):
        if not image_data:
            raise ValueError("image_data cannot be empty")

        self._id = id or UserAvatarUploadId.generate()
        self._user_id = user_id
        self._image_data = image_data
        self._content_type = content_type
        self._created_at = created_at or datetime.now()

    @property
    def id(self) -> UserAvatarUploadId:
        return self._id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def image_data(self) -> bytes:
        return self._image_data

    @property
    def content_type(self) -> str:
        return self._content_type

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @classmethod
    def create(
        cls, user_id: UserId, image_data: bytes, content_type: str = "image/jpeg"
    ) -> "UserAvatarUpload":
        """Factory method para crear un nuevo registro de foto subida."""
        return cls(
            id=UserAvatarUploadId.generate(),
            user_id=user_id,
            image_data=image_data,
            content_type=content_type,
            created_at=datetime.now(),
        )

    def __str__(self) -> str:
        return (
            f"UserAvatarUpload(id={self.id}, user_id={self.user_id}, "
            f"created_at={self.created_at}, size={len(self.image_data)} bytes)"
        )

    def __repr__(self) -> str:
        return self.__str__()
