"""
Caso de Uso: Solicitar Inscripcion (Request Enrollment).

Permite a un jugador solicitar inscribirse en una competicion.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InvalidTeeCategoryError,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.exceptions.competition_violations import (
    DuplicateEnrollmentViolation,
    InvalidCompetitionStatusViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotActiveError(Exception):
    """Excepcion lanzada cuando la competicion no esta en estado ACTIVE."""

    pass


class AlreadyEnrolledError(Exception):
    """Excepcion lanzada cuando el usuario ya tiene una inscripcion en esta competicion."""

    pass


class RequestEnrollmentUseCase:
    """
    Caso de uso para solicitar inscripcion en una competicion.

    Orquesta:
    1. Validacion de existencia de la competicion
    2. Validacion de estado ACTIVE
    3. Validacion de no duplicidad de inscripcion
    4. Creacion del enrollment con estado REQUESTED
    5. Persistencia mediante UoW

    Reglas de negocio:
    - La competicion debe existir
    - La competicion debe estar en estado ACTIVE
    - El usuario no puede tener otra inscripcion activa en la misma competicion
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
        Ejecuta el caso de uso de solicitud de inscripcion.

        Args:
            request: DTO con competition_id y user_id

        Returns:
            DTO con los datos de la inscripcion creada

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            CompetitionNotActiveError: Si la competicion no esta activa
            AlreadyEnrolledError: Si el usuario ya esta inscrito
        """
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            user_id = UserId(request.user_id)

            # 1. Verificar que la competicion existe
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competicion no encontrada: {request.competition_id}"
                )

            # 2. Verificar capacidad disponible
            approved_count = await self._uow.enrollments.count_approved_by_competition(
                competition_id
            )
            CompetitionPolicy.validate_capacity(
                approved_count, competition.max_players, competition_id
            )

            # 3. Business logic guards: Validar enrollment completo (duplicados, limites, temporal, estado)
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
            except DuplicateEnrollmentViolation as e:
                # Type-safe exception handling - no more fragile string matching!
                raise AlreadyEnrolledError(str(e)) from e
            except InvalidCompetitionStatusViolation as e:
                raise CompetitionNotActiveError(str(e)) from e
            # MaxEnrollmentsExceededViolation, EnrollmentPastStartDateViolation propagate as-is

            # 4. Crear enrollment con factory method
            try:
                tee_category = TeeCategory(request.tee_category) if request.tee_category else None
            except ValueError as e:
                raise InvalidTeeCategoryError(
                    f"Valor de tee_category no válido: '{request.tee_category}'. "
                    f"Valores permitidos: {[c.value for c in TeeCategory]}"
                ) from e
            enrollment = Enrollment.request(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=user_id,
                tee_category=tee_category,
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
