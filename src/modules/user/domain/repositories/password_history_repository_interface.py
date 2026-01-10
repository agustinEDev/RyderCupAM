"""
Password History Repository Interface - Domain Layer

Define el contrato para la persistencia de historial de contraseñas.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from ..entities.password_history import PasswordHistory
from ..value_objects.user_id import UserId


class PasswordHistoryRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de historial de contraseñas.

    Define las operaciones necesarias para guardar, consultar y limpiar
    el historial de contraseñas de los usuarios.

    Security (OWASP A07):
        - Limita búsqueda a últimas N contraseñas (default: 5)
        - Soporta limpieza automática de registros antiguos (>1 año)
        - Previene reutilización de contraseñas recientes

    Principios seguidos:
        - Dependency Inversion: El dominio define el contrato
        - Single Responsibility: Solo operaciones de historial de contraseñas
        - Interface Segregation: Métodos específicos y cohesivos
    """

    @abstractmethod
    async def save(self, password_history: PasswordHistory) -> None:
        """
        Guarda un registro de historial de contraseñas.

        Args:
            password_history: El registro a guardar

        Raises:
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def find_recent_by_user(
        self, user_id: UserId, limit: int = 5
    ) -> list[PasswordHistory]:
        """
        Obtiene los N registros más recientes de un usuario.

        Args:
            user_id: ID del usuario
            limit: Número máximo de registros a retornar (default: 5)

        Returns:
            list[PasswordHistory]: Lista ordenada por created_at DESC (más reciente primero)

        Raises:
            RepositoryError: Si ocurre un error de consulta

        Example:
            >>> recent = await repo.find_recent_by_user(user_id, limit=5)
            >>> len(recent) <= 5
            True
        """
        pass

    @abstractmethod
    async def count_by_user(self, user_id: UserId) -> int:
        """
        Cuenta el total de registros de historial para un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            int: Número total de registros

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def delete_old_records(self, older_than: datetime) -> int:
        """
        Elimina registros de historial más antiguos que una fecha.

        Este método se usa para limpieza automática de registros con más de 1 año.

        Args:
            older_than: Fecha límite (registros antes de esta fecha se eliminan)

        Returns:
            int: Número de registros eliminados

        Raises:
            RepositoryError: Si ocurre un error de eliminación

        Example:
            >>> one_year_ago = datetime.now() - timedelta(days=365)
            >>> deleted_count = await repo.delete_old_records(one_year_ago)
            >>> deleted_count >= 0
            True
        """
        pass

    @abstractmethod
    async def delete_by_user(self, user_id: UserId) -> int:
        """
        Elimina todos los registros de historial de un usuario.

        Útil para GDPR compliance (derecho al olvido).

        Args:
            user_id: ID del usuario

        Returns:
            int: Número de registros eliminados

        Raises:
            RepositoryError: Si ocurre un error de eliminación
        """
        pass
