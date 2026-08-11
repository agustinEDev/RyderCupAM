"""
RequestGolfCourseUseCase - Creator solicita un nuevo campo de golf.
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


class RequestGolfCourseUseCase:
    """
    Use Case: Creator solicita un nuevo campo de golf.

    El campo entra en estado PENDING_APPROVAL y dispara un evento
    GolfCourseRequestedEvent que enviará un email al Admin.

    Workflow:
        1. Validar datos (DTOs ya validan estructura)
        2. Crear entidades Tee y Hole
        3. Crear agregado GolfCourse (estado PENDING_APPROVAL)
        4. Persistir vía repositorio
        5. Commit UoW (dispara eventos)

    Args:
        request: DTO con datos del campo a crear
        creator_id: UserId del usuario que solicita el campo

    Returns:
        RequestGolfCourseResponseDTO con el campo creado

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
            request: Datos del campo a solicitar
            creator_id: ID del usuario creador

        Returns:
            Response con el campo creado
        """
        async with self._uow:
            # 1. Convertir DTOs a Value Objects y Entities
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

            # 5. Crear GolfCourse (estado PENDING_APPROVAL)
            golf_course = GolfCourse.create(
                name=request.name,
                country_code=country_code,
                course_type=course_type,
                creator_id=creator_id,
                tees=tees,
                holes=holes,
            )

            # 6. Persistir
            await self._uow.golf_courses.save(golf_course)

            # 7. Mapear a Response DTO (commit automático al salir del context manager)
            response_dto = GolfCourseMapper.to_response_dto(golf_course)

            return RequestGolfCourseResponseDTO(golf_course=response_dto)
