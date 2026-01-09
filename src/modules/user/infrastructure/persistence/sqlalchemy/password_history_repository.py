"""
SQLAlchemy Password History Repository.

Implementación del repositorio de Password History usando SQLAlchemy (async).
"""

from datetime import datetime

from sqlalchemy import delete, select
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

    async def delete_old_records(self, older_than: datetime) -> int:
        """
        Elimina registros de historial más antiguos que una fecha.

        Este método se usa para limpieza automática de registros con más de 1 año.

        Args:
            older_than: Fecha límite (registros antes de esta fecha se eliminan)

        Returns:
            int: Número de registros eliminados

        Notes:
            - Usa índice ix_password_history_created_at para optimizar
            - Puede ejecutarse en background job (cronjob)
        """
        stmt = delete(password_history_table).where(
            password_history_table.c.created_at < older_than
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def delete_by_user(self, user_id: UserId) -> int:
        """
        Elimina todos los registros de historial de un usuario.

        Útil para GDPR compliance (derecho al olvido).
        Normalmente no es necesario porque el Foreign Key tiene CASCADE.

        Args:
            user_id: ID del usuario

        Returns:
            int: Número de registros eliminados
        """
        stmt = delete(password_history_table).where(
            password_history_table.c.user_id == str(user_id.value)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount
