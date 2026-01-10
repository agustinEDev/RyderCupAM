"""
Caso de Uso: Listar Inscripciones (List Enrollments).

Lista las inscripciones de una competición con filtros opcionales.
Retorna entidades (NO DTOs) - siguiendo Clean Architecture.
"""

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class ListEnrollmentsUseCase:
    """
    Caso de uso para listar inscripciones de una competición.

    CLEAN ARCHITECTURE: Este use case retorna ENTIDADES de dominio, NO DTOs.
    La conversión a DTOs es responsabilidad de la capa de presentación (API Layer).

    Orquesta:
    1. Validación de existencia de la competición
    2. Obtención de inscripciones con filtros
    3. Retorno de entidades

    Filtros disponibles:
    - status: Filtrar por estado de inscripción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, competition_id: str, status: str | None = None
    ) -> list[Enrollment]:
        """
        Ejecuta el caso de uso de listado de inscripciones.

        Args:
            competition_id: ID de la competición
            status: Filtro opcional por estado (REQUESTED, APPROVED, etc.)

        Returns:
            Lista de entidades Enrollment

        Raises:
            CompetitionNotFoundError: Si la competición no existe
        """
        async with self._uow:
            comp_id = CompetitionId(competition_id)

            # 1. Verificar que la competición existe
            competition = await self._uow.competitions.find_by_id(comp_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {competition_id}"
                )

            # 2. Obtener enrollments según filtros
            if status:
                # Filtrar por estado
                status_enum = EnrollmentStatus(status.upper())
                enrollments = (
                    await self._uow.enrollments.find_by_competition_and_status(
                        comp_id, status_enum
                    )
                )
            else:
                # Todos los enrollments de la competición
                enrollments = await self._uow.enrollments.find_by_competition(comp_id)

            return enrollments
