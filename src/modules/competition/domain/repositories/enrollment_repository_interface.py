# -*- coding: utf-8 -*-
"""
Enrollment Repository Interface - Domain Layer

Define el contrato para la persistencia de inscripciones siguiendo principios de Clean Architecture.
Esta interfaz pertenece al dominio y será implementada en la capa de infraestructura.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from ..entities.enrollment import Enrollment
from ..value_objects.enrollment_id import EnrollmentId
from ..value_objects.competition_id import CompetitionId
from ..value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId


class EnrollmentRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de inscripciones.

    Define las operaciones CRUD y consultas específicas del dominio de enrollments.
    Esta interfaz es independiente de la implementación de persistencia concreta.

    Principios seguidos:
    - Dependency Inversion: El dominio define el contrato, infraestructura lo implementa
    - Single Responsibility: Solo operaciones relacionadas con persistencia de enrollments
    - Interface Segregation: Métodos específicos y cohesivos
    """

    @abstractmethod
    async def add(self, enrollment: Enrollment) -> None:
        """
        Agrega una nueva inscripción al repositorio.

        Args:
            enrollment: La entidad inscripción a guardar

        Raises:
            EnrollmentAlreadyExistsError: Si ya existe una inscripción con el mismo ID
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def update(self, enrollment: Enrollment) -> None:
        """
        Actualiza una inscripción existente en el repositorio.

        Args:
            enrollment: La entidad inscripción con los datos actualizados

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            RepositoryError: Si ocurre un error de persistencia
        """
        pass

    @abstractmethod
    async def find_by_id(self, enrollment_id: EnrollmentId) -> Optional[Enrollment]:
        """
        Busca una inscripción por su ID único.

        Args:
            enrollment_id: El identificador único de la inscripción

        Returns:
            Optional[Enrollment]: La inscripción encontrada o None si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_competition(
        self,
        competition_id: CompetitionId,
        limit: int = 100,
        offset: int = 0
    ) -> List[Enrollment]:
        """
        Busca todas las inscripciones de una competición específica.

        Útil para: Listar todos los jugadores inscritos en un torneo.

        Args:
            competition_id: El ID de la competición
            limit: Número máximo de inscripciones a retornar (default: 100)
            offset: Número de inscripciones a saltar (default: 0)

        Returns:
            List[Enrollment]: Lista de inscripciones de la competición

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_competition_and_status(
        self,
        competition_id: CompetitionId,
        status: EnrollmentStatus,
        limit: int = 100,
        offset: int = 0
    ) -> List[Enrollment]:
        """
        Busca inscripciones de una competición filtradas por estado.

        Útil para: Listar solo APPROVED para formar equipos, ver REQUESTED pendientes.

        Args:
            competition_id: El ID de la competición
            status: El estado de inscripción (REQUESTED, APPROVED, etc.)
            limit: Número máximo de inscripciones a retornar (default: 100)
            offset: Número de inscripciones a saltar (default: 0)

        Returns:
            List[Enrollment]: Lista de inscripciones con el estado especificado

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_user(
        self,
        user_id: UserId,
        limit: int = 100,
        offset: int = 0
    ) -> List[Enrollment]:
        """
        Busca todas las inscripciones de un usuario específico.

        Útil para: Dashboard del jugador ("Mis inscripciones").

        Args:
            user_id: El ID del usuario
            limit: Número máximo de inscripciones a retornar (default: 100)
            offset: Número de inscripciones a saltar (default: 0)

        Returns:
            List[Enrollment]: Lista de inscripciones del usuario

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def exists_for_user_in_competition(
        self,
        user_id: UserId,
        competition_id: CompetitionId
    ) -> bool:
        """
        Verifica si existe una inscripción para un usuario en una competición específica.

        Útil para: Prevenir inscripción duplicada (mismo usuario, mismo torneo).

        Args:
            user_id: El ID del usuario
            competition_id: El ID de la competición

        Returns:
            bool: True si existe, False si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def count_approved(self, competition_id: CompetitionId) -> int:
        """
        Cuenta el total de inscripciones aprobadas en una competición.

        Útil para: Saber cuántos jugadores están confirmados, validar mínimos/máximos.

        Args:
            competition_id: El ID de la competición

        Returns:
            int: Número total de inscripciones aprobadas

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def count_pending(self, competition_id: CompetitionId) -> int:
        """
        Cuenta el total de inscripciones pendientes (REQUESTED) en una competición.

        Útil para: Mostrar notificaciones al creador sobre solicitudes pendientes.

        Args:
            competition_id: El ID de la competición

        Returns:
            int: Número total de inscripciones con estado REQUESTED

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_by_competition_and_team(
        self,
        competition_id: CompetitionId,
        team_id: str
    ) -> List[Enrollment]:
        """
        Busca todas las inscripciones asignadas a un equipo específico.

        Útil para: Listar jugadores de cada equipo (Team 1 vs Team 2).

        Args:
            competition_id: El ID de la competición
            team_id: El ID del equipo (típicamente "1" o "2")

        Returns:
            List[Enrollment]: Lista de inscripciones del equipo

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass
