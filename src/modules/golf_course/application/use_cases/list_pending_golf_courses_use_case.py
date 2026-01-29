"""
ListPendingGolfCoursesUseCase - Admin lista campos pendientes de aprobación.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ListPendingGolfCoursesRequestDTO,
    ListPendingGolfCoursesResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.shared.infrastructure.persistence.unit_of_work import AbstractUoW


class ListPendingGolfCoursesUseCase:
    """
    Use Case: Lista todos los campos pendientes de aprobación.

    Disponible solo para Admin.
    Retorna campos con approval_status = PENDING_APPROVAL.

    Nota: La validación de rol Admin se hace en la capa API (endpoint).

    Returns:
        ListPendingGolfCoursesResponseDTO con la lista de campos pendientes
    """

    def __init__(self, uow: AbstractUoW) -> None:
        self._uow = uow

    async def execute(
        self,
        request: ListPendingGolfCoursesRequestDTO,
    ) -> ListPendingGolfCoursesResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Request vacío (no requiere parámetros)

        Returns:
            Response con la lista de campos pendientes
        """
        async with self._uow:
            # 1. Obtener campos pendientes
            golf_courses = await self._uow.golf_courses.find_pending_approval()

            # 2. Mapear a Response DTOs
            response_dtos = [GolfCourseMapper.to_response_dto(gc) for gc in golf_courses]

            return ListPendingGolfCoursesResponseDTO(
                golf_courses=response_dtos,
                count=len(response_dtos),
            )
