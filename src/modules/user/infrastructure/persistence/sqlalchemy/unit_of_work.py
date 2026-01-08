from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.repositories.password_history_repository_interface import (
    PasswordHistoryRepositoryInterface,
)
from src.modules.user.domain.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.password_history_repository import (
    SQLAlchemyPasswordHistoryRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_repository import (
    SQLAlchemyRefreshTokenRepository,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)


class SQLAlchemyUnitOfWork(UserUnitOfWorkInterface):
    """
    Implementación asíncrona de la Unit of Work con SQLAlchemy.

    Repositorios incluidos (v1.13.0):
    - users: SQLAlchemyUserRepository
    - refresh_tokens: SQLAlchemyRefreshTokenRepository (Session Timeout)
    - password_history: SQLAlchemyPasswordHistoryRepository (Password History)
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._users = SQLAlchemyUserRepository(session)
        self._refresh_tokens = SQLAlchemyRefreshTokenRepository(session)
        self._password_history = SQLAlchemyPasswordHistoryRepository(session)

    @property
    def users(self) -> UserRepositoryInterface:
        return self._users

    @property
    def refresh_tokens(self) -> RefreshTokenRepositoryInterface:
        return self._refresh_tokens

    @property
    def password_history(self) -> PasswordHistoryRepositoryInterface:
        return self._password_history

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

