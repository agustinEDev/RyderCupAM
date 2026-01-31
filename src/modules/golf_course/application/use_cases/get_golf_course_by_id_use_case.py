"""
GetGolfCourseByIdUseCase - Obtiene un campo de golf por ID.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    GetGolfCourseByIdRequestDTO,
    GetGolfCourseByIdResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class GetGolfCourseByIdUseCase:
    """
    Use Case: Obtiene un campo de golf por ID.

    Disponible para:
        - Admin: puede ver cualquier campo
        - Creator (owner): puede ver sus campos (cualquier estado)
        - Players: solo pueden ver campos APPROVED

    Nota: La validación de permisos se hace en la capa API (endpoint).

    Args:
        request: DTO con golf_course_id

    Returns:
        GetGolfCourseByIdResponseDTO con el campo encontrado

    Raises:
        ValueError: Si el campo no existe
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        request: GetGolfCourseByIdRequestDTO,
    ) -> GetGolfCourseByIdResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: ID del campo a buscar

        Returns:
            Response con el campo encontrado
        """
        async with self._uow:
            # 1. Obtener campo
            golf_course_id = GolfCourseId(request.golf_course_id)
            golf_course = await self._uow.golf_courses.find_by_id(golf_course_id)

            if not golf_course:
                raise ValueError(f"Golf course not found: {request.golf_course_id}")

            # 2. Mapear a Response DTO
            response_dto = GolfCourseMapper.to_response_dto(golf_course)

            return GetGolfCourseByIdResponseDTO(golf_course=response_dto)
