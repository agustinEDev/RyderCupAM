# -*- coding: utf-8 -*-
"""
Competition Repository Interface - Domain Layer

Define el contrato para la persistencia de competiciones siguiendo principios de Clean Architecture.
Esta interfaz pertenece al dominio y será implementada en la capa de infraestructura.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import date
from ..entities.competition import Competition
from ..value_objects.competition_id import CompetitionId
from ..value_objects.competition_name import CompetitionName
from ..value_objects.competition_status import CompetitionStatus
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de competiciones.

    Define las operaciones CRUD y consultas específicas del dominio de torneos.
    Esta interfaz es independiente de la implementación de persistencia concreta.

    Principios seguidos:
    - Dependency Inversion: El dominio define el contrato, infraestructura lo implementa
    - Single Responsibility: Solo operaciones relacionadas con persistencia de competitions
    - Interface Segregation: Métodos específicos y cohesivos
    """

    @abstractmethod
    async def add(self, competition: Competition) -> None:
        """
        Agrega una nueva competición al repositorio.

        Args:
            competition: La entidad competición a guardar

        Raises:
            CompetitionAlreadyExistsError: Si ya existe una competición con el mismo ID
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def update(self, competition: Competition) -> None:
        """
        Actualiza una competición existente en el repositorio.

        Args:
            competition: La entidad competición con los datos actualizados

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def delete(self, competition_id: CompetitionId) -> bool:
        """
        Elimina una competición del repositorio (soft delete recomendado).

        Args:
            competition_id: El identificador único de la competición

        Returns:
            bool: True si se eliminó, False si no existía

        Raises:
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def find_by_id(self, competition_id: CompetitionId) -> Optional[Competition]:
        """
        Busca una competición por su ID único.

        Args:
            competition_id: El identificador único de la competición

        Returns:
            Optional[Competition]: La competición encontrada o None si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_creator(
        self,
        creator_id: UserId,
        limit: int = 100,
        offset: int = 0
    ) -> List[Competition]:
        """
        Busca todas las competiciones creadas por un usuario específico.

        Útil para: Dashboard del creador ("Mis torneos").

        Args:
            creator_id: El ID del usuario creador
            limit: Número máximo de competiciones a retornar (default: 100)
            offset: Número de competiciones a saltar (default: 0)

        Returns:
            List[Competition]: Lista de competiciones del creador

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_status(
        self,
        status: CompetitionStatus,
        limit: int = 100,
        offset: int = 0
    ) -> List[Competition]:
        """
        Busca todas las competiciones con un estado específico.

        Útil para: Admin puede ver todos los torneos ACTIVE, listar DRAFT, etc.

        Args:
            status: El estado de la competición (DRAFT, ACTIVE, etc.)
            limit: Número máximo de competiciones a retornar (default: 100)
            offset: Número de competiciones a saltar (default: 0)

        Returns:
            List[Competition]: Lista de competiciones con el estado especificado

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_active_in_date_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[Competition]:
        """
        Busca competiciones activas que se superpongan con un rango de fechas.

        Útil para: Detectar conflictos de fechas, calendario de torneos.

        Args:
            start_date: Fecha de inicio del rango
            end_date: Fecha de fin del rango

        Returns:
            List[Competition]: Lista de competiciones activas en el rango

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def exists_with_name(
        self,
        name: CompetitionName,
        creator_id: UserId
    ) -> bool:
        """
        Verifica si existe una competición con el nombre especificado para un creador.

        Útil para: Prevenir duplicados por creador (mismo creador, mismo nombre).

        Args:
            name: El nombre de la competición
            creator_id: El ID del usuario creador

        Returns:
            bool: True si existe, False si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[Competition]:
        """
        Obtiene todas las competiciones con paginación.

        Útil para: Listado general de torneos.

        Args:
            limit: Número máximo de competiciones a retornar (default: 100)
            offset: Número de competiciones a saltar (default: 0)

        Returns:
            List[Competition]: Lista de todas las competiciones

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def count_by_creator(self, creator_id: UserId) -> int:
        """
        Cuenta el total de competiciones creadas por un usuario.

        Útil para: Estadísticas, límites de torneos por usuario.

        Args:
            creator_id: El ID del usuario creador

        Returns:
            int: Número total de competiciones del creador

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass
