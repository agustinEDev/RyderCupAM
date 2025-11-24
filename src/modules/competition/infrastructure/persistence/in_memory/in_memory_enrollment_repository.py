# -*- coding: utf-8 -*-
"""In-Memory Enrollment Repository para testing."""

from typing import Dict, List, Optional

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.enrollment_repository_interface import (
    EnrollmentRepositoryInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryEnrollmentRepository(EnrollmentRepositoryInterface):
    """
    Implementación en memoria del repositorio de inscripciones para testing.
    """

    def __init__(self):
        self._enrollments: Dict[EnrollmentId, Enrollment] = {}

    async def add(self, enrollment: Enrollment) -> None:
        """Agrega una nueva inscripción."""
        self._enrollments[enrollment.id] = enrollment

    async def update(self, enrollment: Enrollment) -> None:
        """Actualiza una inscripción existente."""
        if enrollment.id in self._enrollments:
            self._enrollments[enrollment.id] = enrollment

    async def save(self, enrollment: Enrollment) -> None:
        """Guarda o actualiza una inscripción (alias para compatibilidad)."""
        self._enrollments[enrollment.id] = enrollment

    async def find_by_id(self, enrollment_id: EnrollmentId) -> Optional[Enrollment]:
        """Busca una inscripción por su ID."""
        return self._enrollments.get(enrollment_id)

    async def find_by_competition_and_status(
        self,
        competition_id: CompetitionId,
        status: EnrollmentStatus
    ) -> List[Enrollment]:
        """Busca inscripciones de una competición con un estado específico."""
        return [
            enr for enr in self._enrollments.values()
            if enr.competition_id == competition_id and enr.status == status
        ]

    async def exists_for_user_in_competition(
        self,
        user_id: UserId,
        competition_id: CompetitionId
    ) -> bool:
        """Verifica si un usuario ya tiene una inscripción en una competición."""
        return any(
            enr.user_id == user_id and enr.competition_id == competition_id
            for enr in self._enrollments.values()
        )

    async def find_by_competition(
        self,
        competition_id: CompetitionId,
        limit: int = 100,
        offset: int = 0
    ) -> List[Enrollment]:
        """Busca todas las inscripciones de una competición."""
        enrollments = [
            enr for enr in self._enrollments.values()
            if enr.competition_id == competition_id
        ]
        return enrollments[offset:offset + limit]

    async def find_by_user(
        self,
        user_id: UserId,
        limit: int = 100,
        offset: int = 0
    ) -> List[Enrollment]:
        """Busca todas las inscripciones de un usuario."""
        enrollments = [
            enr for enr in self._enrollments.values()
            if enr.user_id == user_id
        ]
        return enrollments[offset:offset + limit]

    async def find_by_competition_and_team(
        self,
        competition_id: CompetitionId,
        team_id: str
    ) -> List[Enrollment]:
        """Busca inscripciones de una competición filtradas por equipo."""
        return [
            enr for enr in self._enrollments.values()
            if enr.competition_id == competition_id and enr.team_id == team_id
        ]

    async def count_approved(self, competition_id: CompetitionId) -> int:
        """Cuenta el número de inscripciones aprobadas (nuevo nombre de método)."""
        return sum(
            1 for enr in self._enrollments.values()
            if enr.competition_id == competition_id and
            enr.status == EnrollmentStatus.APPROVED
        )

    async def count_pending(self, competition_id: CompetitionId) -> int:
        """Cuenta el número de inscripciones pendientes (REQUESTED)."""
        return sum(
            1 for enr in self._enrollments.values()
            if enr.competition_id == competition_id and
            enr.status == EnrollmentStatus.REQUESTED
        )

    async def count_approved_enrollments(
        self,
        competition_id: CompetitionId
    ) -> int:
        """Cuenta el número de inscripciones aprobadas para una competición (alias)."""
        return await self.count_approved(competition_id)

    async def delete(self, enrollment_id: EnrollmentId) -> None:
        """Elimina una inscripción por su ID."""
        if enrollment_id in self._enrollments:
            del self._enrollments[enrollment_id]

    async def find_all(self) -> List[Enrollment]:
        """Retorna todas las inscripciones."""
        return list(self._enrollments.values())
