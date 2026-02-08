"""
Caso de Uso: Inscripcion Directa por Creador (Direct Enroll Player).

Permite al creador de una competicion inscribir directamente a un jugador.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InvalidTeeCategoryError,
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
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


class NotCreatorError(Exception):
    """Excepcion lanzada cuando el usuario no es el creador de la competicion."""

    pass


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

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: DirectEnrollPlayerRequestDTO, creator_id: UserId
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
        """
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            player_id = UserId(request.user_id)

            # 1. Verificar que la competicion existe
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competicion no encontrada: {request.competition_id}"
                )

            # 2. Verificar que es el creador
            if competition.creator_id != creator_id:
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

            # 5. Crear enrollment con factory method (directamente APPROVED)
            try:
                tee_category = TeeCategory(request.tee_category) if request.tee_category else None
            except ValueError as e:
                raise InvalidTeeCategoryError(
                    f"Valor de tee_category no válido: '{request.tee_category}'. "
                    f"Valores permitidos: {[c.value for c in TeeCategory]}"
                ) from e
            enrollment = Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=player_id,
                custom_handicap=request.custom_handicap,
                tee_category=tee_category,
            )

            # 6. Persistir
            await self._uow.enrollments.add(enrollment)

        # 8. Retornar DTO
        return DirectEnrollPlayerResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            custom_handicap=enrollment.custom_handicap,
            created_at=enrollment.created_at,
        )
