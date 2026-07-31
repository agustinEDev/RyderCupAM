"""
In-Memory User Avatar Upload Repository para testing.
"""

from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.repositories.user_avatar_upload_repository_interface import (
    UserAvatarUploadRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryUserAvatarUploadRepository(UserAvatarUploadRepositoryInterface):
    """Implementación en memoria del repositorio de fotos de avatar para tests."""

    def __init__(self):
        self._uploads: dict[str, UserAvatarUpload] = {}

    async def save(self, upload: UserAvatarUpload) -> None:
        self._uploads[str(upload.id.value)] = upload

    async def find_by_id(self, upload_id: UserAvatarUploadId) -> UserAvatarUpload | None:
        return self._uploads.get(str(upload_id.value))

    async def find_by_user(self, user_id: UserId) -> list[UserAvatarUpload]:
        user_uploads = [u for u in self._uploads.values() if u.user_id == user_id]
        user_uploads.sort(key=lambda u: u.created_at, reverse=True)
        return user_uploads

    async def count_by_user(self, user_id: UserId) -> int:
        return len([u for u in self._uploads.values() if u.user_id == user_id])

    async def delete(self, upload_id: UserAvatarUploadId) -> None:
        self._uploads.pop(str(upload_id.value), None)
