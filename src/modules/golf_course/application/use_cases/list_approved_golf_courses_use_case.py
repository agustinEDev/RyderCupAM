"""
ListApprovedGolfCoursesUseCase - Lista todos los campos aprobados.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ListApprovedGolfCoursesRequestDTO,
    ListApprovedGolfCoursesResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.shared.infrastructure.persistence.unit_of_work import AbstractUoW


class ListApprovedGolfCoursesUseCase:
    """
    Use Case: Lista todos los campos de golf aprobados.

    Disponible para todos los usuarios autenticados (Admin/Creator/Player).
    Solo retorna campos con approval_status = APPROVED.

    Returns:
        ListApprovedGolfCoursesResponseDTO con la lista de campos aprobados
    """

    def __init__(self, uow: AbstractUoW) -> None:
        self._uow = uow

    async def execute(
        self,
        request: ListApprovedGolfCoursesRequestDTO,
    ) -> ListApprovedGolfCoursesResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Request vacío (no requiere parámetros)

        Returns:
            Response con la lista de campos aprobados
        """
        async with self._uow:
            # 1. Obtener campos aprobados
            golf_courses = await self._uow.golf_courses.find_approved()

            # 2. Mapear a Response DTOs
            response_dtos = [GolfCourseMapper.to_response_dto(gc) for gc in golf_courses]

            return ListApprovedGolfCoursesResponseDTO(
                golf_courses=response_dtos,
                count=len(response_dtos),
            )
