"""
Caso de Uso: Eliminar Campo de Golf de Competición.

Permite desasociar un campo de golf de una competición en estado DRAFT.
Solo el creador puede realizar esta acción.
"""

from datetime import UTC, datetime

from src.modules.competition.application.dto.competition_dto import (
    RemoveGolfCourseRequestDTO,
    RemoveGolfCourseResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class CompetitionNotDraftError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class GolfCourseNotAssignedError(Exception):
    """Excepción lanzada cuando el campo de golf no está asociado a la competición."""

    pass


class RemoveGolfCourseFromCompetitionUseCase:
    """
    Caso de uso para eliminar un campo de golf de una competición.

    Restricciones:
    - La competición debe estar en estado DRAFT
    - Solo el creador puede eliminar campos
    - El campo debe estar actualmente asociado a la competición

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que esté en estado DRAFT
    4. Eliminar el campo de la competición (validación de existencia en el dominio)
    5. Guardar la competición actualizada
    6. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones de Competition
        """
        self._uow = uow

    async def execute(
        self, request: RemoveGolfCourseRequestDTO, user_id: UserId
    ) -> RemoveGolfCourseResponseDTO:
        """
        Ejecuta el caso de uso de eliminar campo de golf de competición.

        Args:
            request: DTO con competition_id y golf_course_id
            user_id: ID del usuario que solicita la operación

        Returns:
            DTO con confirmación de eliminación

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDraftError: Si la competición no está en estado DRAFT
            GolfCourseNotAssignedError: Si el campo no está asociado a la competición
        """
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede eliminar campos de golf de la competición"
                )

            # 3. Verificar que esté en estado DRAFT
            if not competition.is_draft():
                raise CompetitionNotDraftError(
                    f"Solo se pueden eliminar campos en estado DRAFT. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Eliminar el campo de la competición (validación en dominio)
            golf_course_id = GolfCourseId(request.golf_course_id)
            try:
                competition.remove_golf_course(golf_course_id)
            except ValueError as e:
                # El campo no está asociado
                raise GolfCourseNotAssignedError(str(e)) from e

            # 5. Guardar la competición actualizada
            await self._uow.competitions.update(competition)

        # 6. Construir respuesta
        return RemoveGolfCourseResponseDTO(
            competition_id=request.competition_id,
            golf_course_id=request.golf_course_id,
            removed_at=datetime.now(UTC),
        )
