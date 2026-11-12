"""
SQLAlchemy Password History Repository.

Implementación del repositorio de Password History usando SQLAlchemy (async).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.repositories.password_history_repository_interface import (
    PasswordHistoryRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper import (
    password_history_table,
)


class SQLAlchemyPasswordHistoryRepository(PasswordHistoryRepositoryInterface):
    """
    Implementación SQLAlchemy del repositorio de Password History.

    Usa async/await para operaciones no bloqueantes.
    Sigue el patrón Repository de Clean Architecture.

    Security (OWASP A07):
        - Limita búsquedas a últimas N contraseñas (default: 5)
        - Soporta limpieza automática de registros antiguos (>1 año)
        - Foreign Key CASCADE para GDPR compliance
    """

    def __init__(self, session: AsyncSession):
        """
        Inicializa el repositorio con una sesión de SQLAlchemy.

        Args:
            session: Sesión async de SQLAlchemy
        """
        self._session = session

    async def save(self, password_history: PasswordHistory) -> None:
        """
        Persiste un registro de historial de contraseñas.

        Args:
            password_history: Entidad PasswordHistory a persistir
        """
        self._session.add(password_history)
        await self._session.flush()

    async def find_recent_by_user(self, user_id: UserId, limit: int = 5) -> list[PasswordHistory]:
        """
        Obtiene los N registros más recientes de un usuario.

        Args:
            user_id: ID del usuario
            limit: Número máximo de registros a retornar (default: 5)

        Returns:
            list[PasswordHistory]: Lista ordenada por created_at DESC (más reciente primero)

        Notes:
            - Usa índice compuesto ix_password_history_user_created
            - Retorna lista vacía si el usuario no tiene historial
        """
        stmt = (
            select(PasswordHistory)
            .where(password_history_table.c.user_id == str(user_id.value))
            .order_by(password_history_table.c.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UserId) -> int:
        """
        Cuenta el total de registros de historial para un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            int: Número total de registros
        """
        stmt = select(PasswordHistory).where(password_history_table.c.user_id == str(user_id.value))
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))
