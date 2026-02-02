"""
Caso de Uso: Establecer Hándicap Personalizado (Set Custom Handicap).

Permite al creador establecer un hándicap personalizado para un jugador inscrito.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    SetCustomHandicapRequestDTO,
    SetCustomHandicapResponseDTO,
)
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class EnrollmentNotFoundError(Exception):
    """Excepción lanzada cuando la inscripción no existe."""

    pass


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class NotCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class SetCustomHandicapUseCase:
    """
    Caso de uso para establecer un hándicap personalizado.

    Orquesta:
    1. Validación de existencia del enrollment
    2. Validación de existencia de la competición
    3. Validación de que el solicitante es el creador
    4. Establecer el hándicap personalizado
    5. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el creador puede establecer hándicaps personalizados
    - El hándicap debe estar en rango válido (-10.0 a 54.0)
    - Este valor hace override del hándicap oficial del jugador
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: SetCustomHandicapRequestDTO, creator_id: UserId
    ) -> SetCustomHandicapResponseDTO:
        """
        Ejecuta el caso de uso de establecer hándicap personalizado.

        Args:
            request: DTO con enrollment_id y custom_handicap
            creator_id: ID del usuario que ejecuta la acción (debe ser el creador)

        Returns:
            DTO con los datos actualizados

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si la competición no existe
            NotCreatorError: Si el solicitante no es el creador
            ValueError: Si el hándicap no es válido
        """
        async with self._uow:
            enrollment_id = EnrollmentId(request.enrollment_id)

            # 1. Obtener enrollment
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {request.enrollment_id}")

            # 2. Obtener competición
            competition = await self._uow.competitions.find_by_id(enrollment.competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )

            # 3. Verificar que es el creador
            if competition.creator_id != creator_id:
                raise NotCreatorError(
                    "Solo el creador de la competición puede establecer hándicaps personalizados"
                )

            # 4. Verificar que el enrollment está aprobado
            if not enrollment.is_approved():
                raise EnrollmentStateError(
                    "Solo se puede establecer un hándicap personalizado en inscripciones aprobadas"
                )

            # 5. Establecer hándicap (la entidad valida el rango)
            enrollment.set_custom_handicap(request.custom_handicap)

            # 6. Persistir cambios
            await self._uow.enrollments.update(enrollment)

        # 8. Retornar DTO
        return SetCustomHandicapResponseDTO(
            id=enrollment.id.value,
            custom_handicap=enrollment.custom_handicap,
            updated_at=enrollment.updated_at,
        )
