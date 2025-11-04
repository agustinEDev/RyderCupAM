# src/modules/user/infrastructure/persistence/sqlalchemy/unit_of_work.py
from sqlalchemy.orm import Session
from src.modules.user.domain.repositories.user_unit_of_work_interface import UserUnitOfWorkInterface
from .user_repository import SQLAlchemyUserRepository

class SQLAlchemyUnitOfWork(UserUnitOfWorkInterface):
    """
    Implementación del Unit of Work con SQLAlchemy para el módulo de usuarios.
    """
    def __init__(self, session: Session):
        self._session = session

    async def __aenter__(self):
        # Inicia la transacción. En SQLAlchemy, esto se maneja implícitamente
        # al usar la sesión, pero podemos ser explícitos si es necesario.
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Si salimos del 'with' sin errores, hacemos commit.
        if exc_type is None:
            await self.commit()
        else:
            # Si hubo un error, hacemos rollback.
            await self.rollback()

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()

    @property
    def users(self) -> SQLAlchemyUserRepository:
        """
        Devuelve una instancia del repositorio de usuarios, inyectándole
        la sesión de esta unidad de trabajo.
        """
        return SQLAlchemyUserRepository(self._session)
