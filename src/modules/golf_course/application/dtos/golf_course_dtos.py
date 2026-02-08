"""
Golf Course DTOs - Request/Response for use cases.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.golf_course.domain.value_objects.course_type import CourseType

# ============================================================================
# Nested DTOs (Tee, Hole)
# ============================================================================


class TeeDTO(BaseModel):
    """DTO para representar un tee (salida)."""

    tee_category: str = Field(
        ..., description="Categoría normalizada (CHAMPIONSHIP, AMATEUR, SENIOR, FORWARD, JUNIOR)"
    )
    tee_gender: str | None = Field(None, description="Género del tee (MALE/FEMALE/null)")
    identifier: str = Field(
        ..., description="Identificador libre del campo (Amarillo, Oro, 1, etc.)"
    )
    course_rating: float = Field(..., ge=50.0, le=90.0, description="Course Rating WHS (50-90)")
    slope_rating: int = Field(..., ge=55, le=155, description="Slope Rating WHS (55-155)")

    class Config:
        from_attributes = True


class HoleDTO(BaseModel):
    """DTO para representar un hoyo."""

    hole_number: int = Field(..., ge=1, le=18, description="Número de hoyo (1-18)")
    par: int = Field(..., ge=3, le=5, description="Par del hoyo (3-5)")
    stroke_index: int = Field(..., ge=1, le=18, description="Índice de dificultad (1-18)")

    class Config:
        from_attributes = True


# ============================================================================
# Request DTOs
# ============================================================================


class RequestGolfCourseRequestDTO(BaseModel):
    """Request para solicitar un nuevo campo de golf (Creator)."""

    name: str = Field(..., min_length=3, max_length=200, description="Nombre del campo")
    country_code: str = Field(
        ..., min_length=2, max_length=2, description="Código ISO del país (ES, FR, etc.)"
    )
    course_type: CourseType = Field(..., description="Tipo de campo (STANDARD_18, etc.)")
    tees: list[TeeDTO] = Field(..., min_length=2, max_length=10, description="2-10 tees")
    holes: list[HoleDTO] = Field(
        ..., min_length=18, max_length=18, description="Exactamente 18 hoyos"
    )

    # NOTA: Las validaciones de reglas de negocio (stroke_index únicos, hole_numbers, etc.)
    # están en el dominio (GolfCourse._validate_holes), no aquí.
    # El DTO solo valida la estructura básica del request.


class ApproveGolfCourseRequestDTO(BaseModel):
    """Request para aprobar un campo de golf (Admin)."""

    golf_course_id: str = Field(..., description="ID del campo a aprobar (UUID)")


class RejectGolfCourseRequestDTO(BaseModel):
    """Request para rechazar un campo de golf (Admin)."""

    golf_course_id: str = Field(..., description="ID del campo a rechazar (UUID)")
    reason: str = Field(..., min_length=10, max_length=500, description="Razón del rechazo")


class GetGolfCourseByIdRequestDTO(BaseModel):
    """Request para obtener un campo por ID."""

    golf_course_id: str = Field(..., description="ID del campo (UUID)")


class ListApprovedGolfCoursesRequestDTO(BaseModel):
    """Request para listar campos aprobados (todos los usuarios)."""

    country_code: str | None = Field(None, description="Filtrar por código ISO de país")


class ListPendingGolfCoursesRequestDTO(BaseModel):
    """Request para listar campos pendientes (Admin only)."""

    pass  # No requiere parámetros


# ============================================================================
# Response DTOs
# ============================================================================


class GolfCourseResponseDTO(BaseModel):
    """Response completo de un campo de golf."""

    id: str = Field(..., description="ID del campo (UUID)")
    name: str = Field(..., description="Nombre del campo")
    country_code: str = Field(..., description="Código ISO del país")
    course_type: str = Field(..., description="Tipo de campo")
    creator_id: str = Field(..., description="ID del creador (UUID)")
    tees: list[TeeDTO] = Field(..., description="Lista de tees")
    holes: list[HoleDTO] = Field(..., description="Lista de hoyos")
    approval_status: str = Field(..., description="Estado de aprobación")
    rejection_reason: str | None = Field(None, description="Razón de rechazo (si aplica)")
    total_par: int = Field(..., description="Par total del campo")
    created_at: datetime = Field(..., description="Fecha de creación")
    updated_at: datetime = Field(..., description="Fecha de última actualización")
    original_golf_course_id: str | None = Field(
        None, description="ID del campo original (si este es un clone/update proposal)"
    )
    is_pending_update: bool = Field(
        False, description="TRUE si este campo tiene un clone pendiente de aprobación"
    )

    class Config:
        from_attributes = True


class RequestGolfCourseResponseDTO(BaseModel):
    """Response después de solicitar un campo."""

    golf_course: GolfCourseResponseDTO = Field(..., description="Campo creado")
    message: str = Field(
        default="Golf course request submitted successfully. Awaiting admin approval.",
        description="Mensaje de confirmación",
    )


class ApproveGolfCourseResponseDTO(BaseModel):
    """Response después de aprobar un campo."""

    golf_course: GolfCourseResponseDTO = Field(..., description="Campo aprobado")
    message: str = Field(
        default="Golf course approved successfully.",
        description="Mensaje de confirmación",
    )


class RejectGolfCourseResponseDTO(BaseModel):
    """Response después de rechazar un campo."""

    golf_course: GolfCourseResponseDTO = Field(..., description="Campo rechazado")
    message: str = Field(
        default="Golf course rejected.",
        description="Mensaje de confirmación",
    )


class GetGolfCourseByIdResponseDTO(BaseModel):
    """Response al obtener un campo por ID."""

    golf_course: GolfCourseResponseDTO = Field(..., description="Campo encontrado")


class ListApprovedGolfCoursesResponseDTO(BaseModel):
    """Response al listar campos aprobados."""

    golf_courses: list[GolfCourseResponseDTO] = Field(..., description="Lista de campos aprobados")
    count: int = Field(..., description="Número total de campos")


class ListPendingGolfCoursesResponseDTO(BaseModel):
    """Response al listar campos pendientes."""

    golf_courses: list[GolfCourseResponseDTO] = Field(..., description="Lista de campos pendientes")
    count: int = Field(..., description="Número total de campos")


# ============================================================================
# Update/Edit DTOs (v2.0.2)
# ============================================================================


class UpdateGolfCourseRequestDTO(BaseModel):
    """Request para actualizar un campo de golf existente."""

    name: str = Field(..., min_length=3, max_length=200, description="Nombre del campo")
    country_code: str = Field(
        ..., min_length=2, max_length=2, description="Código ISO del país (ES, FR, etc.)"
    )
    course_type: CourseType = Field(..., description="Tipo de campo (STANDARD_18, etc.)")
    tees: list[TeeDTO] = Field(..., min_length=2, max_length=10, description="2-10 tees")
    holes: list[HoleDTO] = Field(
        ..., min_length=18, max_length=18, description="Exactamente 18 hoyos"
    )


class UpdateGolfCourseResponseDTO(BaseModel):
    """Response después de actualizar un campo de golf."""

    golf_course: GolfCourseResponseDTO = Field(..., description="Campo actualizado")
    message: str = Field(..., description="Mensaje explicando qué pasó (updated vs clone created)")
    pending_update: GolfCourseResponseDTO | None = Field(
        None, description="Clone creado (solo si creator editó campo APPROVED)"
    )


class ApproveUpdateGolfCourseRequestDTO(BaseModel):
    """Request para aprobar un update (clone) de un campo de golf."""

    clone_id: str = Field(..., description="ID del clone a aprobar (UUID)")


class ApproveUpdateGolfCourseResponseDTO(BaseModel):
    """Response después de aprobar un update."""

    updated_golf_course: GolfCourseResponseDTO = Field(
        ..., description="Campo original con cambios aplicados"
    )
    message: str = Field(
        default="Golf course update approved successfully",
        description="Mensaje de confirmación",
    )
    applied_changes_from: str = Field(
        ..., description="ID del clone que fue aplicado (ya eliminado)"
    )


class RejectUpdateGolfCourseRequestDTO(BaseModel):
    """Request para rechazar un update (clone) de un campo de golf."""

    clone_id: str = Field(..., description="ID del clone a rechazar (UUID)")


class RejectUpdateGolfCourseResponseDTO(BaseModel):
    """Response después de rechazar un update."""

    original_golf_course: GolfCourseResponseDTO = Field(
        ..., description="Campo original sin cambios"
    )
    message: str = Field(
        default="Golf course update rejected",
        description="Mensaje de confirmación",
    )
    rejected_clone_id: str = Field(..., description="ID del clone rechazado (eliminado)")
