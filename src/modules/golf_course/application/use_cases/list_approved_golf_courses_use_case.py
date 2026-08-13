"""
ListApprovedGolfCoursesUseCase - Lista todos los campos aprobados.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ListApprovedGolfCoursesRequestDTO,
    ListApprovedGolfCoursesResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    ApprovedCourseSearch,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)


class ListApprovedGolfCoursesUseCase:
    """
    Use Case: Lista todos los campos de golf aprobados.

    Disponible para todos los usuarios autenticados (Admin/Creator/Player).
    Solo retorna campos con approval_status = APPROVED.

    Returns:
        ListApprovedGolfCoursesResponseDTO con la lista de campos aprobados
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        request: ListApprovedGolfCoursesRequestDTO,
    ) -> ListApprovedGolfCoursesResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Request con filtro opcional de país

        Returns:
            Response con la lista de campos aprobados
        """
        async with self._uow:
            # 1. Buscar los campos aprobados que cumplan el filtro
            page = await self._uow.golf_courses.search_approved(
                ApprovedCourseSearch(
                    country_code=request.country_code,
                    name=request.name,
                    limit=request.limit,
                    offset=request.offset,
                    latitude=request.latitude,
                    longitude=request.longitude,
                    radius_km=request.radius_km,
                )
            )

            # 2. Mapear al DTO de listado, que no lleva tarjeta
            summaries = [
                GolfCourseMapper.to_summary_dto(
                    course, distance_km=page.distances_km.get(str(course.id))
                )
                for course in page.courses
            ]

            return ListApprovedGolfCoursesResponseDTO(
                golf_courses=summaries,
                count=len(summaries),
                total=page.total,
            )
