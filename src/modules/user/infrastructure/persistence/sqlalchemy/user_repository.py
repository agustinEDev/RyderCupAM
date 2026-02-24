from sqlalchemy import func, or_, select
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

    MIN_NAME_PARTS = 2

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user: User) -> None:
        """Guarda un usuario en la base de datos."""
        self._session.add(user)

    async def find_by_id(self, user_id: UserId) -> User | None:
        """Busca un usuario por su ID."""
        return await self._session.get(User, user_id)

    async def find_by_email(self, email: Email) -> User | None:
        """Busca un usuario por su email."""
        # Para composites, necesitamos usar where() y comparar con el atributo privado
        statement = select(User).where(User._email == email.value)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_all(self) -> list[User]:
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

    async def find_by_full_name(self, full_name: str) -> User | None:
        """Busca un usuario por su nombre completo."""
        # Separar el nombre completo en palabras para buscar
        name_parts = full_name.strip().split()
        if len(name_parts) < self.MIN_NAME_PARTS:
            return None

        # Buscar por primera coincidencia exacta de first_name + last_name
        for i in range(1, len(name_parts)):
            first_name = " ".join(name_parts[:i])
            last_name = " ".join(name_parts[i:])

            statement = select(User).filter(
                func.lower(User.first_name) == func.lower(first_name),
                func.lower(User.last_name) == func.lower(last_name),
            )
            result = await self._session.execute(statement)
            user = result.scalar_one_or_none()
            if user:
                return user

        return None

    async def search_by_partial_name(self, query: str, limit: int = 10) -> list[User]:
        """Searches users by partial name match using ILIKE. Requires at least 2 characters."""
        query = query.strip()
        if len(query) < self.MIN_NAME_PARTS:
            return []
        statement = (
            select(User)
            .filter(
                or_(
                    func.lower(User.first_name).contains(query.lower(), autoescape=True),
                    func.lower(User.last_name).contains(query.lower(), autoescape=True),
                    func.lower(User.first_name + " " + User.last_name).contains(query.lower(), autoescape=True),
                )
            )
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si un usuario existe por su email."""
        # Para composites, necesitamos usar where() y comparar con el atributo privado
        statement = select(func.count()).select_from(User).where(User._email == email.value)
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def count_all(self) -> int:
        """Cuenta todos los usuarios."""
        statement = select(func.count()).select_from(User)
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def find_by_verification_token(self, token: str) -> User | None:
        """Busca un usuario por su token de verificación."""
        statement = select(User).filter_by(verification_token=token)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_password_reset_token(self, token: str) -> User | None:
        """
        Busca un usuario por su token de reseteo de contraseña.

        Args:
            token: Token de reseteo generado con User.generate_password_reset_token()

        Returns:
            User encontrado o None si no existe

        Note:
            - Usa índice ix_users_password_reset_token para búsqueda rápida
            - NO valida expiración (esa lógica está en User.can_reset_password())
        """
        statement = select(User).filter_by(password_reset_token=token)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
