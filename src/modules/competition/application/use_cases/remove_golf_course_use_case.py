"""
Caso de Uso: Eliminar Campo de Golf de Competicion.

Permite desasociar un campo de golf de una competicion en estado DRAFT.
Solo el creador puede realizar esta accion.
"""

from datetime import UTC, datetime

from src.modules.competition.application.dto.competition_dto import (
    RemoveGolfCourseRequestDTO,
    RemoveGolfCourseResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotDraftError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class GolfCourseNotAssignedError(Exception):
    """Excepcion lanzada cuando el campo de golf no esta asociado a la competicion."""

    pass


class RemoveGolfCourseFromCompetitionUseCase:
    """
    Caso de uso para eliminar un campo de golf de una competicion.

    Restricciones:
    - La competicion debe estar en estado DRAFT
    - Solo el creador puede eliminar campos
    - El campo debe estar actualmente asociado a la competicion

    Orquesta:
    1. Buscar la competicion por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que este en estado DRAFT
    4. Eliminar el campo de la competicion (validacion de existencia en el dominio)
    5. Guardar la competicion actualizada
    6. Commit de la transaccion
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
        Ejecuta el caso de uso de eliminar campo de golf de competicion.

        Args:
            request: DTO con competition_id y golf_course_id
            user_id: ID del usuario que solicita la operacion

        Returns:
            DTO con confirmacion de eliminacion

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDraftError: Si la competicion no esta en estado DRAFT
            GolfCourseNotAssignedError: Si el campo no esta asociado a la competicion
        """
        async with self._uow:
            # 1. Buscar la competicion
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede eliminar campos de golf de la competicion"
                )

            # 3. Verificar que este en estado DRAFT
            if not competition.is_draft():
                raise CompetitionNotDraftError(
                    f"Solo se pueden eliminar campos en estado DRAFT. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Eliminar el campo de la competicion (validacion en dominio)
            golf_course_id = GolfCourseId(request.golf_course_id)
            try:
                competition.remove_golf_course(golf_course_id)
            except ValueError as e:
                # El campo no esta asociado
                raise GolfCourseNotAssignedError(str(e)) from e

            # 5. Guardar la competicion actualizada
            await self._uow.competitions.update(competition)

        # 6. Construir respuesta
        return RemoveGolfCourseResponseDTO(
            competition_id=request.competition_id,
            golf_course_id=request.golf_course_id,
            removed_at=datetime.now(UTC),
        )
