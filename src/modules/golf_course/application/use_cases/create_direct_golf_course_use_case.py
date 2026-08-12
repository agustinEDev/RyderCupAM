"""
CreateDirectGolfCourseUseCase - Admin crea campo directo a APPROVED.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    RequestGolfCourseRequestDTO,
    RequestGolfCourseResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


class CreateDirectGolfCourseUseCase:
    """
    Use Case: Admin crea campo de golf directo a APPROVED.

    Similar a RequestGolfCourseUseCase pero el campo se crea directamente
    en estado APPROVED (sin necesidad de aprobación).

    IMPORTANTE: Solo Admins pueden usar este use case. La autorización
    debe verificarse en el API layer.

    Workflow:
        1. Validar datos (DTOs ya validan estructura)
        2. Crear entidades Tee y Hole
        3. Crear agregado GolfCourse
        4. Aprobar inmediatamente (estado APPROVED)
        5. Persistir vía repositorio
        6. Commit UoW

    Args:
        request: DTO con datos del campo a crear
        creator_id: UserId del admin que crea el campo

    Returns:
        RequestGolfCourseResponseDTO con el campo creado (APPROVED)

    Raises:
        ValueError: Si los datos son inválidos (reglas de dominio)
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        request: RequestGolfCourseRequestDTO,
        creator_id: UserId,
    ) -> RequestGolfCourseResponseDTO:
        """
        Ejecuta el caso de uso.

        Args:
            request: Datos del campo a crear
            creator_id: ID del admin creador

        Returns:
            Response con el campo creado (estado APPROVED)
        """
        async with self._uow:
            # 1. Convertir DTOs a Value Objects
            country_code = CountryCode(request.country_code)
            course_type = request.course_type

            # 2. Validar que el país existe en la BD
            country = await self._uow.countries.find_by_code(country_code)
            if country is None:
                raise ValueError(f"Country with code '{request.country_code}' not found")

            # 3. Crear Tees
            tees = GolfCourseMapper.to_domain_tees(request.tees)

            # 4. Crear Holes
            holes = GolfCourseMapper.to_domain_holes(request.holes)

            # 5. Crear GolfCourse (estado PENDING_APPROVAL primero)
            golf_course = GolfCourse.create(
                name=request.name,
                country_code=country_code,
                course_type=course_type,
                creator_id=creator_id,
                tees=tees,
                holes=holes,
                location=GolfCourseMapper.to_domain_location(request.location),
            )

            # 6. Aprobar inmediatamente (Admin privilege)
            golf_course.approve()

            # 7. Persistir
            await self._uow.golf_courses.save(golf_course)

            # 8. Mapear a Response DTO (commit automático al salir del context manager)
            response_dto = GolfCourseMapper.to_response_dto(golf_course)

            return RequestGolfCourseResponseDTO(golf_course=response_dto)
