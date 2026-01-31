"""
Caso de Uso: Reordenar Campos de Golf en Competición.

Permite cambiar el orden de visualización de los campos de golf asociados a una competición.
Solo el creador puede realizar esta acción.
"""

from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    ReorderGolfCoursesRequestDTO,
    ReorderGolfCoursesResponseDTO,
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


class InvalidReorderError(Exception):
    """Excepción lanzada cuando el reorden no es válido (IDs missing, duplicates, etc.)."""

    pass


class ReorderGolfCoursesUseCase:
    """
    Caso de uso para reordenar los campos de golf de una competición.

    Restricciones:
    - La competición debe estar en estado DRAFT
    - Solo el creador puede reordenar campos
    - La lista de IDs debe incluir TODOS los campos actualmente asociados
    - No puede haber duplicados en la lista
    - Todos los IDs deben existir en la competición

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que esté en estado DRAFT
    4. Convertir UUIDs a GolfCourseId
    5. Reordenar campos (validación de integridad en el dominio)
    6. Guardar la competición actualizada
    7. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones de Competition
        """
        self._uow = uow

    async def execute(
        self, request: ReorderGolfCoursesRequestDTO, user_id: UserId
    ) -> ReorderGolfCoursesResponseDTO:
        """
        Ejecuta el caso de uso de reordenar campos de golf.

        Args:
            request: DTO con competition_id y lista ordenada de golf_course_ids
            user_id: ID del usuario que solicita la operación

        Returns:
            DTO con confirmación de reordenación

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDraftError: Si la competición no está en estado DRAFT
            InvalidReorderError: Si la lista de IDs no es válida (duplicados, missing, extra)
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
                    "Solo el creador puede reordenar campos de golf de la competición"
                )

            # 3. Verificar que esté en estado DRAFT
            if not competition.is_draft():
                raise CompetitionNotDraftError(
                    f"Solo se pueden reordenar campos en estado DRAFT. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Convertir UUIDs a GolfCourseId
            golf_course_ids = [GolfCourseId(uuid) for uuid in request.golf_course_ids]

            # 5. Reordenar campos (validación en dominio)
            try:
                competition.reorder_golf_courses(golf_course_ids)
            except ValueError as e:
                # Puede ser por duplicados, missing IDs, o extra IDs
                raise InvalidReorderError(str(e)) from e

            # 6. Guardar la competición actualizada
            await self._uow.competitions.save(competition)

        # 7. Construir respuesta
        return ReorderGolfCoursesResponseDTO(
            competition_id=request.competition_id,
            golf_course_count=len(golf_course_ids),
            reordered_at=datetime.now(),
        )
