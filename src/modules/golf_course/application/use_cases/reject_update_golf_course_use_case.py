"""
RejectUpdateGolfCourseUseCase - Admin rechaza un update (clone) de campo.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    RejectUpdateGolfCourseRequestDTO,
    RejectUpdateGolfCourseResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class RejectUpdateGolfCourseUseCase:
    """
    Use Case: Admin rechaza un update proposal (clone) de campo de golf.

    Workflow:
        1. Buscar el clone por ID
        2. Verificar que es realmente un clone (tiene original_golf_course_id)
        3. Buscar el campo original
        4. Eliminar el clone
        5. Marcar original como is_pending_update=FALSE (clear mark)
        6. Commit

    IMPORTANTE: Solo Admins pueden ejecutar este use case.
    La autorización debe verificarse en el API layer.

    Args:
        request: DTO con clone_id a rechazar

    Returns:
        RejectUpdateGolfCourseResponseDTO con:
        - original_golf_course: Campo original sin cambios
        - rejected_clone_id: ID del clone rechazado (eliminado)

    Raises:
        ValueError: Si clone no existe, no es clone, o original no existe
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        request: RejectUpdateGolfCourseRequestDTO,
    ) -> RejectUpdateGolfCourseResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Request con clone_id a rechazar

        Returns:
            Response con campo original sin cambios
        """
        async with self._uow:
            # 1. Buscar el clone
            clone_id = GolfCourseId(request.clone_id)
            clone = await self._uow.golf_courses.find_by_id(clone_id)

            if clone is None:
                raise ValueError(f"Golf course clone with ID {clone_id} not found")

            # 2. Verificar que es realmente un clone (tiene original_golf_course_id)
            if clone.original_golf_course_id is None:
                raise ValueError(
                    f"Golf course {clone_id} is not a clone/update proposal. "
                    "It does not have an original_golf_course_id."
                )

            # 3. Buscar campo original
            original_course = await self._uow.golf_courses.find_by_id(clone.original_golf_course_id)

            if original_course is None:
                raise ValueError(f"Original golf course {clone.original_golf_course_id} not found")

            # 4. Quitar marca de "pending update" del original
            original_course.clear_pending_update()

            # 5. Guardar original actualizado
            await self._uow.golf_courses.save(original_course)

            # 6. Eliminar clone
            await self._uow.golf_courses.delete(clone.id)

            # 7. Mapear a Response DTO (commit automático al salir del context manager)
            original_dto = GolfCourseMapper.to_response_dto(original_course)

            return RejectUpdateGolfCourseResponseDTO(
                original_golf_course=original_dto,
                rejected_clone_id=str(clone_id),
            )
