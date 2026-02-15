"""
Caso de Uso: Reordenar Campos de Golf en Competición.

Permite cambiar el orden de visualización de los campos de golf asociados a una competición.
Solo el creador puede realizar esta acción.
"""

from datetime import UTC, datetime

from src.modules.competition.application.dto.competition_dto import (
    ReorderGolfCoursesRequestDTO,
    ReorderGolfCoursesResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotDraftError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class InvalidReorderError(Exception):
    """Excepción lanzada cuando el reorden no es válido (IDs missing, duplicates, etc.)."""

    pass


class ReorderGolfCoursesUseCase:
    """
    Caso de uso para reordenar los campos de golf de una competición.

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Validar reorden via dominio
    4. Reordenar en dos fases (para evitar UNIQUE constraint en BD)
    5. Guardar y commit
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: ReorderGolfCoursesRequestDTO, user_id: UserId
    ) -> ReorderGolfCoursesResponseDTO:
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

            # 3. Convertir UUIDs a tuplas (GolfCourseId, display_order)
            golf_course_ids = [GolfCourseId(uuid) for uuid in request.golf_course_ids]
            new_order = [
                (gc_id, idx + 1) for idx, gc_id in enumerate(golf_course_ids)
            ]

            # 4. Validar via dominio (estado DRAFT + IDs match)
            try:
                competition.validate_reorder(golf_course_ids)
            except CompetitionStateError as e:
                raise CompetitionNotDraftError(str(e)) from e
            except ValueError as e:
                raise InvalidReorderError(str(e)) from e

            # 5. Reordenar en dos fases para evitar UNIQUE constraint violation
            # Fase 1: valores temporales altos
            competition.reorder_golf_courses_phase1(new_order)
            await self._uow.flush()

            # Fase 2: valores finales (1, 2, 3...)
            competition.reorder_golf_courses_phase2(new_order)

            # 6. Guardar
            await self._uow.competitions.update(competition)

        # 7. Respuesta
        return ReorderGolfCoursesResponseDTO(
            competition_id=request.competition_id,
            golf_course_count=len(new_order),
            reordered_at=datetime.now(UTC),
        )
