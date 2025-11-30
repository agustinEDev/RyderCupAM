from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)


class SQLAlchemyUnitOfWork(UserUnitOfWorkInterface):
    """
    Implementación asíncrona de la Unit of Work con SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._users = SQLAlchemyUserRepository(session)

    @property
    def users(self) -> UserRepositoryInterface:
        return self._users

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - maneja commit/rollback automáticamente.

        Clean Architecture: El Use Case no debe manejar transacciones explícitamente.
        El UoW se encarga automáticamente de persistir cambios y publicar eventos.
        """
        if exc_type:
            # Si hubo excepción, hacer rollback
            await self.rollback()
        else:
            # Si todo fue exitoso, hacer commit automáticamente
            await self.commit()

            # Los eventos de dominio se publican automáticamente
            # Nota: Para MVP, los eventos están registrados pero la publicación
            # real se implementará cuando se necesiten event handlers

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def flush(self) -> None:
        await self._session.flush()

    def is_active(self) -> bool:
        return self._session.is_active

