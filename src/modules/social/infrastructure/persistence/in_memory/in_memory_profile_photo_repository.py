"""In-Memory Profile Photo Repository para testing."""

from src.modules.social.domain.entities.profile_photo import ProfilePhoto
from src.modules.social.domain.repositories.profile_photo_repository_interface import (
    ProfilePhotoMetadata,
    ProfilePhotoRepositoryInterface,
)
from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryProfilePhotoRepository(ProfilePhotoRepositoryInterface):
    """Implementacion en memoria del repositorio de fotos de perfil."""

    def __init__(self):
        self._photos: dict[ProfilePhotoId, ProfilePhoto] = {}

    async def add(self, photo: ProfilePhoto) -> None:
        self._photos[photo.id] = photo

    async def find_by_id(self, photo_id: ProfilePhotoId) -> ProfilePhoto | None:
        return self._photos.get(photo_id)

    async def find_metadata_by_user(self, user_id: UserId) -> list[ProfilePhotoMetadata]:
        de_este = [p for p in self._photos.values() if p.user_id == user_id]
        de_este.sort(key=lambda p: p.created_at, reverse=True)
        return [
            ProfilePhotoMetadata(
                id=p.id, user_id=p.user_id, caption=p.caption, created_at=p.created_at
            )
            for p in de_este
        ]

    async def count_by_user(self, user_id: UserId) -> int:
        return len([p for p in self._photos.values() if p.user_id == user_id])

    async def delete(self, photo_id: ProfilePhotoId) -> bool:
        return self._photos.pop(photo_id, None) is not None
