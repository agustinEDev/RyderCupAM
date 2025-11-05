from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyUserRepository(UserRepositoryInterface):
    """
    Implementación asíncrona del repositorio de usuarios con SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user: User) -> None:
        """Guarda un usuario en la base de datos."""
        self._session.add(user)

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Busca un usuario por su ID."""
        return await self._session.get(User, user_id)

    async def find_by_email(self, email: Email) -> Optional[User]:
        """Busca un usuario por su email."""
        statement = select(User).filter_by(email=email)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_all(self) -> List[User]:
        """Devuelve todos los usuarios."""
        statement = select(User)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete_by_id(self, user_id: UserId) -> None:
        """Elimina un usuario por su ID."""
        user = await self.find_by_id(user_id)
        if user:
            await self._session.delete(user)

    async def update(self, user: User) -> None:
        """
        Actualiza un usuario.
        SQLAlchemy lo maneja automáticamente al hacer commit si el objeto ya existe.
        """
        self._session.add(user)

    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si un usuario existe por su email."""
        statement = select(func.count()).select_from(User).filter_by(email=email)
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def count_all(self) -> int:
        """Cuenta todos los usuarios."""
        statement = select(func.count()).select_from(User)
        result = await self._session.execute(statement)
        return result.scalar_one()