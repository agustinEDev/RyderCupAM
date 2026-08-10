"""Profile Photo Repository - SQLAlchemy Implementation."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.social.domain.entities.profile_photo import ProfilePhoto
from src.modules.social.domain.repositories.profile_photo_repository_interface import (
    ProfilePhotoMetadata,
    ProfilePhotoRepositoryInterface,
)
from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.social.infrastructure.persistence.mappers.profile_photo_mapper import (
    profile_photos_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyProfilePhotoRepository(ProfilePhotoRepositoryInterface):
    """Implementacion asincrona del repositorio de fotos de perfil."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, photo: ProfilePhoto) -> None:
        self._session.add(photo)

    async def find_by_id(self, photo_id: ProfilePhotoId) -> ProfilePhoto | None:
        return await self._session.get(ProfilePhoto, photo_id)

    async def find_metadata_by_user(self, user_id: UserId) -> list[ProfilePhotoMetadata]:
        """
        La galeria sin las imagenes.

        Se seleccionan columnas sueltas en lugar de la entidad a proposito: pedir
        `ProfilePhoto` traeria tambien `image_data`, y diez fotos son casi cuatro
        megas movidos para enseñar una lista de pies de foto.
        """
        stmt = (
            select(
                profile_photos_table.c.id,
                profile_photos_table.c.user_id,
                profile_photos_table.c.caption,
                profile_photos_table.c.created_at,
            )
            .where(profile_photos_table.c.user_id == user_id)
            .order_by(profile_photos_table.c.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [
            ProfilePhotoMetadata(
                id=row.id, user_id=row.user_id, caption=row.caption, created_at=row.created_at
            )
            for row in result.all()
        ]

    async def count_by_user(self, user_id: UserId) -> int:
        stmt = (
            select(func.count())
            .select_from(profile_photos_table)
            .where(profile_photos_table.c.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def delete(self, photo_id: ProfilePhotoId) -> bool:
        stmt = delete(profile_photos_table).where(profile_photos_table.c.id == photo_id)
        result = await self._session.execute(stmt)
        return bool(result.rowcount)
