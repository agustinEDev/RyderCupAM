"""
GetGolfCourseByIdUseCase - Obtiene un campo de golf por ID.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    GetGolfCourseByIdRequestDTO,
    GetGolfCourseByIdResponseDTO,
)
from src.modules.golf_course.application.exceptions import GolfCourseMissingError
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class GetGolfCourseByIdUseCase:
    """
    Use Case: Obtiene un campo de golf por ID.

    Disponible para:
        - Admin: puede ver cualquier campo
        - Creator (owner): puede ver sus campos (cualquier estado)
        - Players: solo pueden ver campos APPROVED

    Args:
        request: DTO con golf_course_id

    Returns:
        GetGolfCourseByIdResponseDTO con el campo encontrado

    Raises:
        GolfCourseMissingError: Si el campo no existe, o si no está aprobado y quien
            lo pide no es admin ni quien lo propuso
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
                raise GolfCourseMissingError(f"Golf course not found: {request.golf_course_id}")

            # 2. Uno sin aprobar solo lo ven un admin y quien lo propuso. A los demás se
            # les responde como si no existiera: un 403 les diría que hay un campo
            # pendiente con ese id (OWASP A01, 17 nov 2026)
            if (
                golf_course.approval_status != ApprovalStatus.APPROVED
                and not request.requester_is_admin
                and str(golf_course.creator_id) != request.requester_id
            ):
                raise GolfCourseMissingError(f"Golf course not found: {request.golf_course_id}")

            # 3. Mapear a Response DTO
            response_dto = GolfCourseMapper.to_response_dto(golf_course)

            return GetGolfCourseByIdResponseDTO(golf_course=response_dto)
