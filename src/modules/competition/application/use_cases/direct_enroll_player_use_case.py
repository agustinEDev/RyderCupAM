"""
Caso de Uso: Inscripcion Directa por Creador (Direct Enroll Player).

Permite al creador de una competicion inscribir directamente a un jugador.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionFullError,
    CompetitionNotFoundError,
    InvalidTeeColorError,
    NotCreatorError,
)
from src.modules.competition.application.services.genero_obligatorio import exigir_genero
from src.modules.competition.application.services.handicap_obligatorio import exigir_handicap
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    al_ocupar_una_plaza,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotActiveError(Exception):
    """Excepcion lanzada cuando la competicion no esta en estado ACTIVE."""

    pass


class AlreadyEnrolledError(Exception):
    """Excepcion lanzada cuando el usuario ya tiene una inscripcion en esta competicion."""

    pass


class DirectEnrollPlayerUseCase:
    """
    Caso de uso para inscripcion directa por el creador.

    Orquesta:
    1. Validacion de existencia de la competicion
    2. Validacion de que el solicitante es el creador
    3. Validacion de estado ACTIVE
    4. Validacion de no duplicidad
    5. Creacion del enrollment con estado APPROVED
    6. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el creador puede inscribir directamente
    - La competicion debe estar en estado ACTIVE
    - El jugador no puede estar ya inscrito
    - Se puede asignar un handicap personalizado opcionalmente
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

    async def execute(
        self, request: DirectEnrollPlayerRequestDTO, creator_id: UserId, is_admin: bool = False
    ) -> DirectEnrollPlayerResponseDTO:
        """
        Ejecuta el caso de uso de inscripcion directa.

        Args:
            request: DTO con competition_id, user_id y custom_handicap opcional
            creator_id: ID del usuario que ejecuta la accion (debe ser el creador)

        Returns:
            DTO con los datos de la inscripcion creada

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCreatorError: Si el solicitante no es el creador
            CompetitionNotActiveError: Si no esta activa
            AlreadyEnrolledError: Si el jugador ya esta inscrito
            CompetitionFullError: Si no quedan plazas
        """
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            player_id = UserId(request.user_id)

            # 1. Verificar que la competicion existe
            # Con la fila bloqueada: sin ella, inscribir a la vez que se cierra
            # leía «abierta» y metía a alguien tras el cierre (#710)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competicion no encontrada: {request.competition_id}"
                )

            # 2. Verificar que es el creador
            if not is_admin and competition.creator_id != creator_id:
                raise NotCreatorError(
                    "Solo el creador de la competicion puede inscribir jugadores directamente"
                )

            # 3. Verificar estado ACTIVE
            if competition.status != CompetitionStatus.ACTIVE:
                raise CompetitionNotActiveError(
                    f"La competicion no esta abierta para inscripciones. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Verificar que el jugador no esta ya inscrito
            already_enrolled = await self._uow.enrollments.exists_for_user_in_competition(
                player_id, competition_id
            )
            if already_enrolled:
                raise AlreadyEnrolledError(
                    "El jugador ya tiene una inscripcion en esta competicion"
                )

            # 5. Con plaza: la misma regla que aceptar una invitación y aprobar una
            # solicitud. Sin ella, el organizador podía pasar del cupo del torneo
            # y el sorteo y los partidos trabajaban con más jugadores (BE #325)
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

            # Sin género no se sabe desde qué barras juega (#710)
            await exigir_genero(self._user_repo, player_id, es_quien_se_apunta=False)
            # Y en un Stableford o un Medal, un hándicap: el suyo o el que le pongan (#251)
            await exigir_handicap(
                self._user_repo,
                competition,
                player_id,
                es_quien_se_apunta=False,
                personalizado=request.custom_handicap,
            )

            # 6. Crear enrollment con factory method (directamente APPROVED)
            try:
                tee_color = TeeColor(request.tee_color) if request.tee_color else None
            except ValueError as e:
                raise InvalidTeeColorError(
                    f"Valor de tee_color no válido: '{request.tee_color}'. "
                    f"Valores permitidos: {[c.value for c in TeeColor]}"
                ) from e
            enrollment = Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=player_id,
                custom_handicap=request.custom_handicap,
                tee_color=tee_color,
            )

            # 7. Persistir
            await self._uow.enrollments.add(enrollment)

            # Si era la última plaza, las invitaciones pendientes se quedan sin
            # ella ya (BE #359)
            await al_ocupar_una_plaza(
                self._uow, competition_id, approved_count, competition.max_players
            )

        # 8. Retornar DTO
        return DirectEnrollPlayerResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            custom_handicap=enrollment.custom_handicap,
            created_at=enrollment.created_at,
        )
