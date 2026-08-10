"""Entidad: ProfilePhoto — una foto de la galeria de un jugador."""

from datetime import datetime

from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.user.domain.value_objects.user_id import UserId

# Tope de fotos por perfil. A 375 KB cada una son ~7,3 MB por jugador: 200
# jugadores ocupan 1,4 GB de los 10 GB contratados (BE #177).
#
# No lo limita el disco sino la señal acordada para sacar las imagenes de la
# base de datos —tabla por encima de 2 GB—, que con este tope se alcanza sobre
# los 280 jugadores en lugar de los 560 que daban 10 fotos. Sigue siendo margen
# de sobra para una aplicacion entre amigos, y migrar entonces es mover bytes,
# no rehacer nada.
MAX_PHOTOS_PER_PROFILE = 20


class ProfilePhoto:
    """
    Una foto que un jugador ha subido a su perfil.

    Vive en el modulo social y no junto a los avatares porque **su visibilidad
    es una regla social**: la ficha de alguien la ve cualquiera, pero sus fotos
    solo sus amigos. El avatar es lo contrario —identidad publica, hace falta
    para reconocerlo en una busqueda— y por eso se quedan separados.

    La imagen es inmutable: no se edita una foto, se borra y se sube otra. Eso
    es lo que permite cachearla para siempre en el cliente, porque unos bytes
    servidos bajo un id nunca van a cambiar.

    El caption es lo unico editable, y es opcional: la mayoria de fotos no
    necesitan pie.
    """

    def __init__(
        self,
        id: ProfilePhotoId | None,
        user_id: UserId,
        image_data: bytes,
        content_type: str,
        caption: str | None = None,
        created_at: datetime | None = None,
    ):
        if not image_data:
            raise ValueError("image_data cannot be empty")
        if not isinstance(user_id, UserId):
            raise TypeError("user_id must be a UserId")

        self._id = id or ProfilePhotoId.generate()
        self._user_id = user_id
        self._image_data = image_data
        self._content_type = content_type
        self._caption = self._clean_caption(caption)
        self._created_at = created_at or datetime.now()

    @classmethod
    def create(
        cls,
        user_id: UserId,
        image_data: bytes,
        content_type: str = "image/jpeg",
        caption: str | None = None,
    ) -> "ProfilePhoto":
        return cls(
            id=ProfilePhotoId.generate(),
            user_id=user_id,
            image_data=image_data,
            content_type=content_type,
            caption=caption,
        )

    @classmethod
    def reconstruct(cls, **props) -> "ProfilePhoto":
        return cls(**props)

    # === Getters ===

    @property
    def id(self) -> ProfilePhotoId:
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
    def caption(self) -> str | None:
        return self._caption

    @property
    def created_at(self) -> datetime:
        return self._created_at

    # === Reglas ===

    def belongs_to(self, user_id: UserId) -> bool:
        """Si la foto es de ese jugador. Lo comprueba quien intenta borrarla."""
        return self._user_id == user_id

    @staticmethod
    def _clean_caption(caption: str | None) -> str | None:
        """
        Un pie en blanco es lo mismo que no tener pie.

        Se normaliza aqui para que la base de datos no acabe con una mezcla de
        NULL y cadenas vacias que signifiquen lo mismo.
        """
        if caption is None:
            return None
        limpio = caption.strip()
        return limpio or None

    def __eq__(self, other) -> bool:
        return isinstance(other, ProfilePhoto) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"<ProfilePhoto {self._id} user={self._user_id.value}>"
