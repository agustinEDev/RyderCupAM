# src/modules/user/infrastructure/persistence/sqlalchemy/user_repository.py
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.value_objects.email import Email

class SQLAlchemyUserRepository(UserRepositoryInterface):
    """
    Implementación del repositorio de usuarios con SQLAlchemy.
    """
    def __init__(self, session: Session):
        self._session = session

    async def save(self, user: User) -> None:
        """Guarda o actualiza un usuario. SQLAlchemy maneja esto con 'merge'."""
        self._session.merge(user)

    async def find_by_id(self, user_id: UserId) -> Optional[User]:
        """Busca un usuario por su ID."""
        statement = select(User).filter_by(id=user_id)
        return self._session.execute(statement).scalar_one_or_none()

    async def find_by_email(self, email: Email) -> Optional[User]:
        """Busca un usuario por su email."""
        statement = select(User).filter_by(email=email)
        return self._session.execute(statement).scalar_one_or_none()

    async def exists_by_email(self, email: Email) -> bool:
        """Verifica si un usuario existe por su email."""
        statement = select(func.count()).select_from(User).filter_by(email=email)
        count = self._session.execute(statement).scalar()
        return count > 0

    async def update(self, user: User) -> None:
        """Actualiza un usuario. 'merge' también sirve para esto."""
        # En SQLAlchemy, 'merge' inserta si no existe o actualiza si existe.
        # Es una forma segura de manejar la operación de guardado/actualización.
        self._session.merge(user)

    async def delete_by_id(self, user_id: UserId) -> bool:
        """Elimina un usuario por su ID."""
        user = await self.find_by_id(user_id)
        if user:
            self._session.delete(user)
            return True
        return False

    async def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Obtiene una lista paginada de usuarios."""
        statement = select(User).offset(offset).limit(limit)
        return self._session.execute(statement).scalars().all()

    async def count_all(self) -> int:
        """Cuenta el total de usuarios."""
        statement = select(func.count()).select_from(User)
        return self._session.execute(statement).scalar()
