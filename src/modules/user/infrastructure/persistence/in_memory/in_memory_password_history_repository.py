"""
In-Memory Password History Repository para testing.

Implementación en memoria del repositorio de historial de contraseñas.
"""

from datetime import datetime

from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.repositories.password_history_repository_interface import (
    PasswordHistoryRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryPasswordHistoryRepository(PasswordHistoryRepositoryInterface):
    """
    Implementación en memoria del repositorio de Password History para tests.
    """

    def __init__(self):
        """Inicializa el repositorio con un diccionario vacío."""
        self._history: dict[str, PasswordHistory] = {}

    async def save(self, password_history: PasswordHistory) -> None:
        """
        Guarda un registro de historial en memoria.

        Args:
            password_history: Registro a guardar
        """
        self._history[str(password_history.id.value)] = password_history

    async def find_recent_by_user(self, user_id: UserId, limit: int = 5) -> list[PasswordHistory]:
        """
        Obtiene los N registros más recientes de un usuario.

        Args:
            user_id: ID del usuario
            limit: Número máximo de registros

        Returns:
            Lista ordenada por created_at DESC (más reciente primero)
        """
        # Filtrar por user_id
        user_history = [h for h in self._history.values() if h.user_id == user_id]

        # Ordenar por created_at DESC (más reciente primero)
        user_history.sort(key=lambda h: h.created_at, reverse=True)

        # Limitar a N registros
        return user_history[:limit]

    async def count_by_user(self, user_id: UserId) -> int:
        """
        Cuenta el total de registros de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Número total de registros
        """
        return len([h for h in self._history.values() if h.user_id == user_id])

    async def delete_old_records(self, older_than: datetime) -> int:
        """
        Elimina registros más antiguos que una fecha.

        Args:
            older_than: Fecha límite

        Returns:
            Número de registros eliminados
        """
        to_delete = [h_id for h_id, h in self._history.items() if h.created_at < older_than]

        for h_id in to_delete:
            del self._history[h_id]

        return len(to_delete)

    async def delete_by_user(self, user_id: UserId) -> int:
        """
        Elimina todos los registros de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Número de registros eliminados
        """
        to_delete = [h_id for h_id, h in self._history.items() if h.user_id == user_id]

        for h_id in to_delete:
            del self._history[h_id]

        return len(to_delete)
