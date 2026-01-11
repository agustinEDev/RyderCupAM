"""
Caso de Uso: Manejar Solicitud de Inscripción (Handle Enrollment).

Permite al creador aprobar o rechazar una solicitud de inscripción.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
    HandleEnrollmentResponseDTO,
)
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


class InvalidActionError(Exception):
    """Excepción lanzada cuando la acción no es válida."""

    pass


class HandleEnrollmentUseCase:
    """
    Caso de uso para aprobar o rechazar solicitudes de inscripción.

    Orquesta:
    1. Validación de existencia del enrollment
    2. Validación de existencia de la competición
    3. Validación de que el solicitante es el creador
    4. Ejecución de la acción (approve/reject)
    5. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el creador puede aprobar/rechazar
    - El enrollment debe estar en estado REQUESTED o INVITED
    - Las acciones válidas son APPROVE y REJECT
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: HandleEnrollmentRequestDTO, creator_id: UserId
    ) -> HandleEnrollmentResponseDTO:
        """
        Ejecuta el caso de uso de manejo de inscripción.

        Args:
            request: DTO con enrollment_id y action (APPROVE/REJECT)
            creator_id: ID del usuario que ejecuta la acción (debe ser el creador)

        Returns:
            DTO con los datos de la inscripción actualizada

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si la competición no existe
            NotCreatorError: Si el solicitante no es el creador
            InvalidActionError: Si la acción no es válida
            EnrollmentStateError: Si la transición de estado no es válida
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
                    "Solo el creador de la competición puede aprobar o rechazar inscripciones"
                )

            # 4. Ejecutar acción
            if request.action == "APPROVE":
                enrollment.approve()
            elif request.action == "REJECT":
                enrollment.reject()
            else:
                raise InvalidActionError(
                    f"Acción no válida: {request.action}. Use 'APPROVE' o 'REJECT'"
                )

            # 5. Persistir cambios
            await self._uow.enrollments.update(enrollment)

            # 6. Commit
            await self._uow.commit()

        # 7. Retornar DTO
        return HandleEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            updated_at=enrollment.updated_at,
        )
