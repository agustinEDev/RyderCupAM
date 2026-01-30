"""
ApproveUpdateGolfCourseUseCase - Admin aprueba un update (clone) de campo.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ApproveUpdateGolfCourseRequestDTO,
    ApproveUpdateGolfCourseResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class ApproveUpdateGolfCourseUseCase:
    """
    Use Case: Admin aprueba un update proposal (clone) de campo de golf.

    Workflow:
        1. Buscar el clone por ID
        2. Verificar que es realmente un clone (tiene original_golf_course_id)
        3. Buscar el campo original
        4. Aplicar cambios del clone al original (copy all fields)
        5. Eliminar el clone
        6. Marcar original como is_pending_update=FALSE
        7. Commit

    IMPORTANTE: Solo Admins pueden ejecutar este use case.
    La autorización debe verificarse en el API layer.

    Args:
        request: DTO con clone_id a aprobar

    Returns:
        ApproveUpdateGolfCourseResponseDTO con:
        - updated_golf_course: Campo original con cambios aplicados
        - applied_changes_from: ID del clone (ya eliminado)

    Raises:
        ValueError: Si clone no existe, no es clone, o original no existe
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        request: ApproveUpdateGolfCourseRequestDTO,
    ) -> ApproveUpdateGolfCourseResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Request con clone_id a aprobar

        Returns:
            Response con campo original actualizado
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
            original_course = await self._uow.golf_courses.find_by_id(
                clone.original_golf_course_id
            )

            if original_course is None:
                raise ValueError(
                    f"Original golf course {clone.original_golf_course_id} not found"
                )

            # 4. Aplicar cambios del clone al original
            original_course.apply_changes_from_clone(clone)

            # 5. Guardar original actualizado
            await self._uow.golf_courses.save(original_course)

            # 6. Eliminar clone
            await self._uow.golf_courses.delete(clone)

            # 7. Commit
            await self._uow.commit()

            # 8. Mapear a Response DTO
            updated_dto = GolfCourseMapper.to_response_dto(original_course)

            return ApproveUpdateGolfCourseResponseDTO(
                updated_golf_course=updated_dto,
                applied_changes_from=str(clone_id),
            )
