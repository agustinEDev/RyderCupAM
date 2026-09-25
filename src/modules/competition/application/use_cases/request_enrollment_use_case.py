"""
Caso de Uso: Solicitar Inscripcion (Request Enrollment).

Permite a un jugador solicitar inscribirse en una competicion.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionFullError,
    CompetitionNotFoundError,
    InvalidTeeColorError,
)
from src.modules.competition.application.services.genero_obligatorio import exigir_genero
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
    DuplicateEnrollmentViolation,
    EnrollmentPastStartDateViolation,
    InvalidCompetitionStatusViolation,
    MaxEnrollmentsExceededViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import (
    MAX_ENROLLMENTS_PER_USER,
    CompetitionPolicy,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotActiveError(Exception):
    """Excepcion lanzada cuando la competicion no esta en estado ACTIVE."""

    pass


class CompetitionIsPrivateError(Exception):
    """En una competicion privada se entra porque el organizador invita.

    Pedir plaza por cuenta propia solo vale en las publicas (BE #318).
    """

    pass


class AlreadyEnrolledError(Exception):
    """Excepcion lanzada cuando el usuario ya tiene una inscripcion en esta competicion."""

    pass


# Los «no» de la política que antes se escapaban sin traducir y llegaban como un
# 500 mudo: sin cabeceras de CORS, el navegador lo ve como un fallo de red y el
# jugador no se entera de nada (BE #372). El de «llena» es compartido con aprobar
class EnrollmentClosedError(Exception):
    """El torneo ya ha empezado: pasado su primer día no se pide plaza."""


class TooManyEnrollmentsError(Exception):
    """Quien pide ya está en el máximo de competiciones a la vez."""


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

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow
        # El género es obligatorio para apuntarse (#710)
        self._user_repo = user_repository

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

            # 2. En una privada no se pide sitio: se entra porque te invitan.
            # Antes de esto, cualquiera podia llamar a la puerta de la Ryder de
            # unos amigos y el organizador tenia que ir rechazando a mano (BE #318)
            if not competition.accepts_enrollment_requests():
                raise CompetitionIsPrivateError(
                    f"La competición {request.competition_id} es privada: "
                    f"solo se entra por invitación."
                )

            # 3. Verificar capacidad disponible
            approved_count = await self._uow.enrollments.count_approved_by_competition(
                competition_id
            )
            try:
                CompetitionPolicy.validate_capacity(
                    approved_count, competition.max_players, competition_id
                )
            except CompetitionFullViolation as e:
                raise CompetitionFullError(
                    f"La competición está completa: {competition.max_players} plazas ocupadas."
                ) from e

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
            except EnrollmentPastStartDateViolation as e:
                raise EnrollmentClosedError(
                    "El torneo ya ha empezado: no se admiten más inscripciones."
                ) from e
            except MaxEnrollmentsExceededViolation as e:
                raise TooManyEnrollmentsError(
                    f"Ya estás en {MAX_ENROLLMENTS_PER_USER} competiciones, el máximo a la vez."
                ) from e

            # Sin género no se sabe desde qué barras juega (#710)
            await exigir_genero(self._user_repo, user_id, es_quien_se_apunta=True)

            # 4. Crear enrollment con factory method
            try:
                tee_color = TeeColor(request.tee_color) if request.tee_color else None
            except ValueError as e:
                raise InvalidTeeColorError(
                    f"Valor de tee_color no válido: '{request.tee_color}'. "
                    f"Valores permitidos: {[c.value for c in TeeColor]}"
                ) from e
            enrollment = Enrollment.request(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=user_id,
                tee_color=tee_color,
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
