"""
Caso de Uso: Retirar Inscripción (Withdraw Enrollment).

Permite a un jugador aprobado retirarse de una competición.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class EnrollmentNotFoundError(Exception):
    """Excepción lanzada cuando la inscripción no existe."""

    pass


class NotOwnerError(Exception):
    """Excepción lanzada cuando el usuario no es el dueño de la inscripción."""

    pass


class WithdrawEnrollmentUseCase:
    """
    Caso de uso para retirarse de una competición.

    Orquesta:
    1. Validación de existencia del enrollment
    2. Validación de que el solicitante es el dueño
    3. Ejecución del retiro
    4. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el dueño del enrollment puede retirarse
    - Solo se puede retirar desde estado APPROVED
    - Diferencia con cancel: withdraw es después de estar inscrito
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: WithdrawEnrollmentRequestDTO, user_id: UserId
    ) -> WithdrawEnrollmentResponseDTO:
        """
        Ejecuta el caso de uso de retiro de inscripción.

        Args:
            request: DTO con enrollment_id y reason opcional
            user_id: ID del usuario que ejecuta la acción (debe ser el dueño)

        Returns:
            DTO con los datos de la inscripción retirada

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            NotOwnerError: Si el solicitante no es el dueño
            EnrollmentStateError: Si no se puede retirar desde el estado actual
        """
        async with self._uow:
            enrollment_id = EnrollmentId(request.enrollment_id)

            # 1. Obtener enrollment
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(
                    f"Inscripción no encontrada: {request.enrollment_id}"
                )

            # 2. Verificar que es el dueño
            if enrollment.user_id != user_id:
                raise NotOwnerError("Solo puedes retirarte de tu propia inscripción")

            # 3. Withdraw (la entidad valida el estado)
            enrollment.withdraw(request.reason)

            # 4. Persistir cambios
            await self._uow.enrollments.update(enrollment)

            # 5. Commit
            await self._uow.commit()

        # 6. Retornar DTO
        return WithdrawEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            updated_at=enrollment.updated_at,
        )
