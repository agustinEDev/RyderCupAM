"""
UpdateGolfCourseUseCase - Actualizar campo de golf existente.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    UpdateGolfCourseRequestDTO,
    UpdateGolfCourseResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


class UpdateGolfCourseUseCase:
    """
    Use Case: Actualizar un campo de golf existente.

    Orquesta la actualización delegando la decisión de negocio
    (in-place vs clone) a GolfCourse.apply_update().

    Authorization:
        - Admin puede editar cualquier campo (PENDING o APPROVED)
        - Creator solo puede editar sus propios campos
        - Campos REJECTED no son editables
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(
        self,
        golf_course_id: GolfCourseId,
        request: UpdateGolfCourseRequestDTO,
        user_id: UserId,
        is_admin: bool,
    ) -> UpdateGolfCourseResponseDTO:
        """Ejecuta el caso de uso."""
        async with self._uow:
            # 1. Buscar campo original
            original_course = await self._uow.golf_courses.find_by_id(golf_course_id)
            if original_course is None:
                raise ValueError(f"Golf course with ID {golf_course_id} not found")

            # 2. Validar permisos
            if not is_admin and original_course.creator_id != user_id:
                raise ValueError(
                    f"User {user_id} does not have permission to edit golf course {golf_course_id}"
                )

            # 3. Validar que el país existe
            country_code = CountryCode(request.country_code)
            country = await self._uow.countries.find_by_code(country_code)
            if country is None:
                raise ValueError(f"Country with code '{request.country_code}' not found")

            # 4. Crear Tees y Holes desde DTOs
            tees = [
                Tee(
                    category=TeeCategory(tee_dto.tee_category),
                    gender=Gender(tee_dto.tee_gender) if tee_dto.tee_gender else None,
                    identifier=tee_dto.identifier,
                    course_rating=tee_dto.course_rating,
                    slope_rating=tee_dto.slope_rating,
                )
                for tee_dto in request.tees
            ]

            holes = [
                Hole(
                    number=hole_dto.hole_number,
                    par=hole_dto.par,
                    stroke_index=hole_dto.stroke_index,
                )
                for hole_dto in request.holes
            ]

            # 5. Delegar decisión de negocio al dominio
            # apply_update retorna None (in-place) o GolfCourse clone (proposal)
            clone = original_course.apply_update(
                name=request.name,
                country_code=country_code,
                course_type=request.course_type,
                tees=tees,
                holes=holes,
                is_admin=is_admin,
            )

            # 6. Guardar
            await self._uow.golf_courses.save(original_course)

            if clone is not None:
                # Creator + APPROVED → clone creado
                await self._uow.golf_courses.save(clone)

                original_dto = GolfCourseMapper.to_response_dto(original_course)
                clone_dto = GolfCourseMapper.to_response_dto(clone)

                return UpdateGolfCourseResponseDTO(
                    golf_course=original_dto,
                    message="Changes submitted for admin approval. Original golf course remains active.",
                    pending_update=clone_dto,
                )

            # In-place update
            response_dto = GolfCourseMapper.to_response_dto(original_course)
            message = (
                "Golf course updated successfully (admin privileges)"
                if is_admin and original_course.approval_status == ApprovalStatus.APPROVED
                else "Pending golf course updated successfully"
            )

            return UpdateGolfCourseResponseDTO(
                golf_course=response_dto,
                message=message,
                pending_update=None,
            )
