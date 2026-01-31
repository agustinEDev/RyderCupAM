"""
UpdateGolfCourseUseCase - Actualizar campo de golf existente.
"""

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    UpdateGolfCourseRequestDTO,
    UpdateGolfCourseResponseDTO,
)
from src.modules.golf_course.application.mappers.golf_course_mapper import GolfCourseMapper
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
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


class UpdateGolfCourseUseCase:
    """
    Use Case: Actualizar un campo de golf existente.

    LÓGICA DE OPCIÓN A+ (campo original siempre visible):

    **Caso 1: Admin edita campo APPROVED:**
    - Actualiza in-place
    - El campo permanece APPROVED
    - Cambios inmediatos

    **Caso 2: Creator edita su campo APPROVED:**
    - Crea un CLONE con estado PENDING_APPROVAL
    - El campo original permanece APPROVED y visible
    - Original se marca con is_pending_update=TRUE
    - Clone tiene original_golf_course_id apuntando al original
    - Admin debe aprobar el clone para aplicar cambios

    **Caso 3: Creator/Admin edita campo PENDING_APPROVAL:**
    - Actualiza in-place
    - Permanece PENDING_APPROVAL

    **Caso 4: Campo REJECTED:**
    - NO se puede editar (debe crear nueva solicitud)

    Authorization:
        - Admin puede editar cualquier campo (PENDING o APPROVED)
        - Creator solo puede editar sus propios campos
        - Campos REJECTED no son editables

    Args:
        golf_course_id: ID del campo a editar
        request: Nuevos datos del campo
        user_id: ID del usuario que solicita la edición
        is_admin: TRUE si el usuario es Admin

    Returns:
        UpdateGolfCourseResponseDTO con:
        - golf_course: campo actualizado o original sin cambios
        - pending_update: clone creado (solo si creator editó APPROVED)
        - message: explicación de qué pasó

    Raises:
        ValueError: Si el campo no existe, está REJECTED, o usuario sin permisos
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
        """
        Ejecuta el caso de uso.

        Args:
            golf_course_id: ID del campo a actualizar
            request: Nuevos datos
            user_id: Usuario que solicita el cambio
            is_admin: Si el usuario es Admin

        Returns:
            Response con campo actualizado o clone creado
        """
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

            # 3. Validar que no esté REJECTED
            if original_course.approval_status == ApprovalStatus.REJECTED:
                raise ValueError(
                    "Cannot edit a REJECTED golf course. Please create a new request instead."
                )

            # 4. Validar que el país existe
            country_code = CountryCode(request.country_code)
            country = await self._uow.countries.find_by_code(country_code)
            if country is None:
                raise ValueError(f"Country with code '{request.country_code}' not found")

            # 5. Crear Tees y Holes desde DTOs
            tees = [
                Tee(
                    category=TeeCategory(tee_dto.tee_category),
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

            # 6. DECISIÓN: ¿Actualizar in-place o crear clone?
            if is_admin:
                # CASO 1 y 3: Admin siempre actualiza in-place
                original_course.update(
                    name=request.name,
                    country_code=country_code,
                    course_type=request.course_type,
                    tees=tees,
                    holes=holes,
                )
                await self._uow.golf_courses.save(original_course)
                await self._uow.commit()

                response_dto = GolfCourseMapper.to_response_dto(original_course)
                message = (
                    "Golf course updated successfully (admin privileges)"
                    if original_course.approval_status == ApprovalStatus.APPROVED
                    else "Pending golf course updated successfully"
                )

                return UpdateGolfCourseResponseDTO(
                    golf_course=response_dto,
                    message=message,
                    pending_update=None,
                )

            if original_course.approval_status == ApprovalStatus.PENDING_APPROVAL:
                # CASO 3: Creator edita su propio campo PENDING → in-place
                original_course.update(
                    name=request.name,
                    country_code=country_code,
                    course_type=request.course_type,
                    tees=tees,
                    holes=holes,
                )
                await self._uow.golf_courses.save(original_course)
                await self._uow.commit()

                response_dto = GolfCourseMapper.to_response_dto(original_course)

                return UpdateGolfCourseResponseDTO(
                    golf_course=response_dto,
                    message="Pending golf course updated successfully",
                    pending_update=None,
                )

            # CASO 2: Creator edita su campo APPROVED → crear CLONE
            # El original permanece APPROVED y visible

            # Crear clone como si fuera nuevo campo
            clone = GolfCourse.create(
                name=request.name,
                country_code=country_code,
                course_type=request.course_type,
                creator_id=original_course.creator_id,  # Mismo creator
                tees=tees,
                holes=holes,
            )

            # Marcar clone como update proposal (reconstruir con campos especiales)
            clone_reconstructed = GolfCourse.reconstruct(
                id=clone.id,
                name=clone.name,
                country_code=clone.country_code,
                course_type=clone.course_type,
                creator_id=clone.creator_id,
                tees=clone.tees,
                holes=clone.holes,
                approval_status=ApprovalStatus.PENDING_APPROVAL,
                rejection_reason=None,
                created_at=clone.created_at,
                updated_at=clone.updated_at,
                original_golf_course_id=golf_course_id,  # Link al original
                is_pending_update=False,
            )

            # Marcar original como "tiene cambios pendientes"
            original_course.mark_as_pending_update()

            # Guardar ambos
            await self._uow.golf_courses.save(clone_reconstructed)
            await self._uow.golf_courses.save(original_course)
            await self._uow.commit()

            original_dto = GolfCourseMapper.to_response_dto(original_course)
            clone_dto = GolfCourseMapper.to_response_dto(clone_reconstructed)

            return UpdateGolfCourseResponseDTO(
                golf_course=original_dto,
                message="Changes submitted for admin approval. Original golf course remains active.",
                pending_update=clone_dto,
            )
