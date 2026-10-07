"""
Caso de Uso: Listar Inscripciones (List Enrollments).

Lista las inscripciones de una competicion con filtros opcionales.
Retorna entidades (NO DTOs) - siguiendo Clean Architecture.
"""

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Desde que se cierran las inscripciones, el hándicap de cada uno está fijado (#251)
HANDICAP_FIJADO = frozenset(
    {CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED}
)


class ListEnrollmentsUseCase:
    """
    Caso de uso para listar inscripciones de una competicion.

    CLEAN ARCHITECTURE: Este use case retorna ENTIDADES de dominio, NO DTOs.
    La conversion a DTOs es responsabilidad de la capa de presentacion (API Layer).

    Orquesta:
    1. Validacion de existencia de la competicion
    2. Obtencion de inscripciones con filtros
    3. Retorno de entidades

    Filtros disponibles:
    - status: Filtrar por estado de inscripcion
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(self, competition_id: str, status: str | None = None) -> list[Enrollment]:
        """
        Ejecuta el caso de uso de listado de inscripciones.

        Args:
            competition_id: ID de la competicion
            status: Filtro opcional por estado (REQUESTED, APPROVED, etc.)

        Returns:
            Lista de entidades Enrollment

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
        """
        async with self._uow:
            comp_id = CompetitionId(competition_id)

            # 1. Verificar que la competicion existe
            competition = await self._uow.competitions.find_by_id(comp_id)
            if not competition:
                raise CompetitionNotFoundError(f"Competicion no encontrada: {competition_id}")

            # 2. Obtener enrollments segun filtros
            if status:
                # Filtrar por estado
                status_enum = EnrollmentStatus(status.upper())
                enrollments = await self._uow.enrollments.find_by_competition_and_status(
                    comp_id, status_enum
                )
            else:
                # Todos los enrollments de la competicion
                enrollments = await self._uow.enrollments.find_by_competition(comp_id)

            return enrollments

    async def execute_con_categorias(
        self, competition_id: str, status: str | None = None
    ) -> tuple[list[Enrollment], dict[UserId, int | None]]:
        """
        Las inscripciones y, en un stroke play con el hándicap ya fijado (desde
        que se cierran las inscripciones), la categoría de cada aprobado (#251).

        La categoría sale de los hándicaps fijados de TODOS los aprobados, con la
        regla de los seis: no se puede calcular inscripción a inscripción.

        Returns:
            Las inscripciones, y la categoría de cada jugador (vacío si no toca)
        """
        enrollments = await self.execute(competition_id, status)
        async with self._uow:
            comp_id = CompetitionId(competition_id)
            competition = await self._uow.competitions.find_by_id(comp_id)
            if (
                competition is None
                or competition.stroke_play is None
                or competition.status not in HANDICAP_FIJADO
            ):
                return enrollments, {}
            aprobados = await self._uow.enrollments.find_by_competition_and_status(
                comp_id, EnrollmentStatus.APPROVED
            )
        return enrollments, competition.stroke_play.categorias(
            {e.user_id: e.fixed_handicap for e in aprobados}
        )
