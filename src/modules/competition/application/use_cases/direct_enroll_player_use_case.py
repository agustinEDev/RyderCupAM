"""
Caso de Uso: Inscripción Directa por Creador (Direct Enroll Player).

Permite al creador de una competición inscribir directamente a un jugador.
"""

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
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


class NotCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class CompetitionNotActiveError(Exception):
    """Excepción lanzada cuando la competición no está en estado ACTIVE."""

    pass


class AlreadyEnrolledError(Exception):
    """Excepción lanzada cuando el usuario ya tiene una inscripción en esta competición."""

    pass


class DirectEnrollPlayerUseCase:
    """
    Caso de uso para inscripción directa por el creador.

    Orquesta:
    1. Validación de existencia de la competición
    2. Validación de que el solicitante es el creador
    3. Validación de estado ACTIVE
    4. Validación de no duplicidad
    5. Creación del enrollment con estado APPROVED
    6. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el creador puede inscribir directamente
    - La competición debe estar en estado ACTIVE
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
        Ejecuta el caso de uso de inscripción directa.

        Args:
            request: DTO con competition_id, user_id y custom_handicap opcional
            creator_id: ID del usuario que ejecuta la acción (debe ser el creador)

        Returns:
            DTO con los datos de la inscripción creada

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCreatorError: Si el solicitante no es el creador
            CompetitionNotActiveError: Si no está activa
            AlreadyEnrolledError: Si el jugador ya está inscrito
        """
        async with self._uow:
            competition_id = CompetitionId(request.competition_id)
            player_id = UserId(request.user_id)

            # 1. Verificar que la competición existe
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {request.competition_id}"
                )

            # 2. Verificar que es el creador
            if competition.creator_id != creator_id:
                raise NotCreatorError(
                    "Solo el creador de la competición puede inscribir jugadores directamente"
                )

            # 3. Verificar estado ACTIVE
            if competition.status != CompetitionStatus.ACTIVE:
                raise CompetitionNotActiveError(
                    f"La competición no está abierta para inscripciones. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Verificar que el jugador no está ya inscrito
            already_enrolled = (
                await self._uow.enrollments.exists_for_user_in_competition(
                    player_id, competition_id
                )
            )
            if already_enrolled:
                raise AlreadyEnrolledError(
                    "El jugador ya tiene una inscripción en esta competición"
                )

            # 5. Crear enrollment con factory method (directamente APPROVED)
            enrollment = Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=competition_id,
                user_id=player_id,
                custom_handicap=request.custom_handicap,
            )

            # 6. Persistir
            await self._uow.enrollments.add(enrollment)

            # 7. Commit
            await self._uow.commit()

        # 8. Retornar DTO
        return DirectEnrollPlayerResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            custom_handicap=enrollment.custom_handicap,
            created_at=enrollment.created_at,
        )
