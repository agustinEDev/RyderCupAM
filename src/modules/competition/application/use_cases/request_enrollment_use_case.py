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
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.exceptions.business_rule_violation import BusinessRuleViolation


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

    async def execute(self, request: RequestEnrollmentRequestDTO) -> RequestEnrollmentResponseDTO:
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

            # 2. Verificar capacidad disponible
            approved_count = await self._uow.enrollments.count_approved_by_competition(
                competition_id
            )
            CompetitionPolicy.validate_capacity(
                approved_count, competition.max_players, competition_id
            )

            # 3. Business logic guards: Validar enrollment completo (duplicados, límites, temporal, estado)
            existing_enrollment = await self._uow.enrollments.find_by_user_and_competition(
                user_id, competition_id
            )
            user_total_enrollments = await self._uow.enrollments.count_active_by_user(user_id)

            try:
                CompetitionPolicy.can_enroll(
                    user_id=user_id,
                    competition_id=competition_id,
                    existing_enrollment_id=(
                        str(existing_enrollment.id.value) if existing_enrollment else None
                    ),
                    competition_status=competition.status,
                    competition_start_date=competition.dates.start_date,
                    user_total_enrollments=user_total_enrollments,
                )
            except BusinessRuleViolation as e:
                error_msg = str(e).lower()
                # Convertir BusinessRuleViolation a excepciones específicas para compatibilidad
                if "already enrolled" in error_msg:
                    raise AlreadyEnrolledError(str(e)) from e
                if "competition status" in error_msg or "only allowed in" in error_msg:
                    raise CompetitionNotActiveError(str(e)) from e
                # Otras BusinessRuleViolation se propagan tal cual
                raise

            # 4. Crear enrollment con factory method
            enrollment = Enrollment.request(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=user_id,
            )

            # 5. Persistir
            await self._uow.enrollments.add(enrollment)


        # 7. Retornar DTO
        return RequestEnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            created_at=enrollment.created_at,
        )
