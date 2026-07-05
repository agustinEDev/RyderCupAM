"""
Caso de Uso: Eliminar Handicap Personalizado (Remove Custom Handicap).

Permite al creador revertir el handicap personalizado de un jugador, volviendo a usar
su handicap oficial (el del perfil, actualizado vía RFEG en los flujos ya existentes
de login y generación de partidos).
"""

from src.modules.competition.application.dto.enrollment_dto import (
    RemoveCustomHandicapResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
    HandicapEditNotAllowedError,
    NotCreatorError,
)
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class RemoveCustomHandicapUseCase:
    """
    Caso de uso para eliminar el handicap personalizado de un jugador.

    Orquesta:
    1. Validacion de existencia del enrollment
    2. Validacion de existencia de la competicion
    3. Validacion de que el solicitante es el creador (o admin)
    4. Validacion de que el enrollment esta aprobado
    5. Validacion de que la competicion permite editar handicaps (DRAFT/ACTIVE/CLOSED)
    6. Eliminar el handicap personalizado (vuelve a usarse el handicap oficial)
    7. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el creador (o admin) puede eliminar handicaps personalizados
    - Solo se permite mientras la competicion esta en DRAFT, ACTIVE o CLOSED
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, enrollment_id: str, creator_id: UserId, is_admin: bool = False
    ) -> RemoveCustomHandicapResponseDTO:
        """
        Ejecuta el caso de uso de eliminar handicap personalizado.

        Args:
            enrollment_id: ID de la inscripcion
            creator_id: ID del usuario que ejecuta la accion (debe ser el creador)
            is_admin: Si el usuario es admin (bypass del check de creador)

        Returns:
            DTO con los datos actualizados (custom_handicap=None)

        Raises:
            EnrollmentNotFoundError: Si la inscripcion no existe
            CompetitionNotFoundError: Si la competicion no existe
            NotCreatorError: Si el solicitante no es el creador ni admin
            EnrollmentStateError: Si el enrollment no esta aprobado
            HandicapEditNotAllowedError: Si la competicion no permite editar handicaps
        """
        async with self._uow:
            eid = EnrollmentId(enrollment_id)

            # 1. Obtener enrollment
            enrollment = await self._uow.enrollments.find_by_id(eid)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripcion no encontrada: {enrollment_id}")

            # 2. Obtener competicion
            competition = await self._uow.competitions.find_by_id(enrollment.competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competicion no encontrada: {enrollment.competition_id}"
                )

            # 3. Verificar que es el creador
            if not is_admin and competition.creator_id != creator_id:
                raise NotCreatorError(
                    "Solo el creador de la competicion puede eliminar handicaps personalizados"
                )

            # 4. Verificar que el enrollment esta aprobado
            if not enrollment.is_approved():
                raise EnrollmentStateError(
                    "Solo se puede eliminar el handicap personalizado de inscripciones aprobadas"
                )

            # 5. Verificar que la competicion permite editar handicaps (DRAFT/ACTIVE/CLOSED)
            if not competition.status.allows_handicap_edits():
                raise HandicapEditNotAllowedError(
                    "El hándicap personalizado solo puede modificarse mientras la competición "
                    f"está en DRAFT, ACTIVE o CLOSED. Estado actual: {competition.status.value}"
                )

            # 6. Eliminar handicap personalizado
            enrollment.remove_custom_handicap()

            # 7. Persistir cambios
            await self._uow.enrollments.update(enrollment)

        # 8. Retornar DTO
        return RemoveCustomHandicapResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            custom_handicap=enrollment.custom_handicap,
            updated_at=enrollment.updated_at,
        )
