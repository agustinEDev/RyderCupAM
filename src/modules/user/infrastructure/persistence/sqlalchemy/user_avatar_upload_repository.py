"""
SQLAlchemy User Avatar Upload Repository.

Implementación del repositorio de fotos de avatar usando SQLAlchemy (async).
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.repositories.user_avatar_upload_repository_interface import (
    UserAvatarUploadRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.user_avatar_upload_mapper import (
    user_avatar_uploads_table,
)


class SQLAlchemyUserAvatarUploadRepository(UserAvatarUploadRepositoryInterface):
    """Implementación SQLAlchemy del repositorio de fotos de avatar."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, upload: UserAvatarUpload) -> None:
        self._session.add(upload)
        await self._session.flush()

    async def find_by_id(self, upload_id: UserAvatarUploadId) -> UserAvatarUpload | None:
        stmt = select(UserAvatarUpload).where(
            user_avatar_uploads_table.c.id == str(upload_id.value)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: UserId) -> list[UserAvatarUpload]:
        stmt = (
            select(UserAvatarUpload)
            .where(user_avatar_uploads_table.c.user_id == str(user_id.value))
            .order_by(user_avatar_uploads_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UserId) -> int:
        stmt = select(UserAvatarUpload).where(
            user_avatar_uploads_table.c.user_id == str(user_id.value)
        )
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))

    async def delete(self, upload_id: UserAvatarUploadId) -> None:
        stmt = delete(user_avatar_uploads_table).where(
            user_avatar_uploads_table.c.id == str(upload_id.value)
        )
        await self._session.execute(stmt)
        await self._session.flush()
