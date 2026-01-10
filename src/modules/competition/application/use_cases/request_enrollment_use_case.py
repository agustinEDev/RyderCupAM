"""
Caso de Uso: Solicitar Inscripción (Request Enrollment).

Permite a un jugador solicitar inscribirse en una competición.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class CompetitionNotActiveError(Exception):
    """Excepción lanzada cuando la competición no está en estado ACTIVE."""

    pass


class AlreadyEnrolledError(Exception):
    """Excepción lanzada cuando el usuario ya tiene una inscripción en esta competición."""

    pass


class RequestEnrollmentUseCase:
    """
    Caso de uso para solicitar inscripción en una competición.

    Orquesta:
    1. Validación de existencia de la competición
    2. Validación de estado ACTIVE
    3. Validación de no duplicidad de inscripción
    4. Creación del enrollment con estado REQUESTED
    5. Persistencia mediante UoW

    Reglas de negocio:
    - La competición debe existir
    - La competición debe estar en estado ACTIVE
    - El usuario no puede tener otra inscripción activa en la misma competición
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: RequestEnrollmentRequestDTO
    ) -> RequestEnrollmentResponseDTO:
        """
        Ejecuta el caso de uso de solicitud de inscripción.

        Args:
            request: DTO con competition_id y user_id

        Returns:
            DTO con los datos de la inscripción creada

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            CompetitionNotActiveError: Si la competición no está activa
            AlreadyEnrolledError: Si el usuario ya está inscrito
        """
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            user_id = UserId(request.user_id)

            # 1. Verificar que la competición existe
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {request.competition_id}"
                )

            # 2. Verificar que está en estado ACTIVE
            if competition.status != CompetitionStatus.ACTIVE:
                raise CompetitionNotActiveError(
                    f"La competición no está abierta para inscripciones. "
                    f"Estado actual: {competition.status.value}"
                )

            # 3. Verificar que el usuario no está ya inscrito
            already_enrolled = (
                await self._uow.enrollments.exists_for_user_in_competition(
                    user_id, competition_id
                )
            )
            if already_enrolled:
                raise AlreadyEnrolledError(
                    "El usuario ya tiene una inscripción en esta competición"
                )

            # 4. Crear enrollment con factory method
            enrollment = Enrollment.request(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=user_id,
            )

            # 5. Persistir
            await self._uow.enrollments.add(enrollment)

            # 6. Commit
            await self._uow.commit()

        # 7. Retornar DTO
        return RequestEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            created_at=enrollment.created_at,
        )
