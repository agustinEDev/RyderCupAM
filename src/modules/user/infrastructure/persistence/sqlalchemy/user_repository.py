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

    async def find_by_id_for_update(self, user_id: UserId) -> User | None:
        """
        Busca un usuario por su ID con bloqueo de fila (SELECT ... FOR UPDATE).

        Serializa transacciones concurrentes sobre el mismo usuario (p.ej. subidas
        de avatar simultáneas) para que operaciones read-modify-write como podar
        el historial FIFO no se pisen entre sí.
        """
        return await self._session.get(User, user_id, with_for_update=True)

    async def find_by_ids(self, user_ids: list[UserId]) -> list[User]:
        """Busca múltiples usuarios por sus IDs en una sola consulta."""
        if not user_ids:
            return []
        statement = select(User).where(User._id.in_([str(uid) for uid in user_ids]))  # type: ignore[union-attr]
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_email(self, email: Email) -> User | None:
        """Busca un usuario por su email."""
        # _email es un composite(Email, "_email_value"): comparar contra el VO completo
        statement = select(User).where(User._email == email)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    def _search_filter(self, search: str | None):
        """Construye la condición ILIKE compartida por find_all/count_all."""
        if not search or not search.strip():
            return None
        q = search.strip().lower()
        return or_(
            func.lower(User._first_name).contains(q, autoescape=True),
            func.lower(User._last_name).contains(q, autoescape=True),
            func.lower(User._first_name + " " + User._last_name).contains(q, autoescape=True),
            func.lower(User._email_value).contains(q, autoescape=True),
        )

    def _build_filters(
        self,
        search: str | None,
        is_admin: bool | None,
        is_active: bool | None,
        email_verified: bool | None,
    ) -> list:
        conditions = []
        search_condition = self._search_filter(search)
        if search_condition is not None:
            conditions.append(search_condition)
        if is_admin is not None:
            conditions.append(User._is_admin == is_admin)
        if is_active is not None:
            conditions.append(User._is_active == is_active)
        if email_verified is not None:
            conditions.append(User._email_verified == email_verified)
        return conditions

    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        is_admin: bool | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
    ) -> list[User]:
        """Devuelve una página de usuarios, opcionalmente filtrada."""
        statement = select(User).order_by(User._created_at.desc())
        for condition in self._build_filters(search, is_admin, is_active, email_verified):
            statement = statement.where(condition)
        statement = statement.limit(limit).offset(offset)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete_by_id(self, user_id: UserId) -> bool:
        """Elimina un usuario por su ID. Devuelve True si existía y se eliminó."""
        user = await self.find_by_id(user_id)
        if not user:
            return False
        await self._session.delete(user)
        return True

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
                func.lower(User._first_name) == func.lower(first_name),
                func.lower(User._last_name) == func.lower(last_name),
            )
            result = await self._session.execute(statement)
            user = result.scalar_one_or_none()
            if user:
                return user

        return None

    MIN_SEARCH_LENGTH = 2

    async def search_by_partial_name(self, query: str, limit: int = 10) -> list[User]:
        """Searches users by partial name match using ILIKE. Requires at least 2 characters."""
        query = query.strip()
        if len(query) < self.MIN_SEARCH_LENGTH:
            return []
        q = query.lower()
        statement = (
            select(User)
            .filter(
                or_(
                    func.lower(User._first_name).contains(q, autoescape=True),
                    func.lower(User._last_name).contains(q, autoescape=True),
                    func.lower(User._first_name + " " + User._last_name).contains(
                        q, autoescape=True
                    ),
                )
            )
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si un usuario existe por su email."""
        # _email es un composite(Email, "_email_value"): comparar contra el VO completo
        statement = select(func.count()).select_from(User).where(User._email == email)
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def count_all(
        self,
        search: str | None = None,
        is_admin: bool | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
    ) -> int:
        """Cuenta usuarios, opcionalmente filtrados (ver find_all)."""
        statement = select(func.count()).select_from(User)
        for condition in self._build_filters(search, is_admin, is_active, email_verified):
            statement = statement.where(condition)
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def find_by_verification_token(self, token: str) -> User | None:
        """Busca un usuario por su token de verificación."""
        statement = select(User).filter_by(_verification_token=token)
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
        statement = select(User).filter_by(_password_reset_token=token)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
