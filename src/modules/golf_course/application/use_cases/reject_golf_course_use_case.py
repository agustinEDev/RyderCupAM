"""
RejectGolfCourseUseCase - Admin rechaza un campo de golf.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    RejectGolfCourseRequestDTO,
    RejectGolfCourseResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class RejectGolfCourseUseCase:
    """
    Use Case: Admin rechaza un campo de golf.

    El campo pasa de PENDING_APPROVAL → REJECTED y dispara un evento
    GolfCourseRejectedEvent que enviará un email bilingüe al Creator
    con la razón del rechazo.

    Workflow:
        1. Obtener campo por ID
        2. Validar que exista
        3. Llamar a domain method reject(reason)
        4. Persistir cambios
        5. Commit UoW (dispara eventos)

    Args:
        request: DTO con golf_course_id y reason

    Returns:
        RejectGolfCourseResponseDTO con el campo rechazado

    Raises:
        ValueError: Si el campo no existe o no se puede rechazar
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        request: RejectGolfCourseRequestDTO,
    ) -> RejectGolfCourseResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Datos de rechazo (ID + razón)

        Returns:
            Response con el campo rechazado
        """
        async with self._uow:
            # 1. Obtener campo
            golf_course_id = GolfCourseId(request.golf_course_id)
            golf_course = await self._uow.golf_courses.find_by_id(golf_course_id)

            if not golf_course:
                raise ValueError(f"Golf course not found: {request.golf_course_id}")

            # 2. Rechazar (domain method valida estado y razón)
            golf_course.reject(reason=request.reason)

            # 3. Persistir
            await self._uow.golf_courses.save(golf_course)

            # 4. Mapear a Response DTO (commit automático al salir del context manager)
            response_dto = GolfCourseMapper.to_response_dto(golf_course)

            return RejectGolfCourseResponseDTO(golf_course=response_dto)
