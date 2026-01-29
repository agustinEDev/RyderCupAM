"""
Golf Course DTOs - Request/Response for use cases.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.modules.golf_course.domain.value_objects.course_type import CourseType

# ============================================================================
# Nested DTOs (Tee, Hole)
# ============================================================================


class TeeDTO(BaseModel):
    """DTO para representar un tee (salida)."""

    tee_category: str = Field(..., description="Categoría normalizada (CHAMPIONSHIP_MALE, etc.)")
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
    tees: list[TeeDTO] = Field(..., min_length=2, max_length=6, description="2-6 tees")
    holes: list[HoleDTO] = Field(
        ..., min_length=18, max_length=18, description="Exactamente 18 hoyos"
    )

    @field_validator("holes")
    @classmethod
    def validate_hole_numbers(cls, holes: list[HoleDTO]) -> list[HoleDTO]:
        """Valida que los hoyos estén numerados 1-18."""
        hole_numbers = [h.hole_number for h in holes]
        if sorted(hole_numbers) != list(range(1, 19)):
            raise ValueError("Holes must be numbered 1-18")
        return holes

    @field_validator("holes")
    @classmethod
    def validate_stroke_indices(cls, holes: list[HoleDTO]) -> list[HoleDTO]:
        """Valida que los stroke indices sean únicos 1-18."""
        stroke_indices = [h.stroke_index for h in holes]
        if len(stroke_indices) != len(set(stroke_indices)):
            raise ValueError("Stroke indices must be unique")
        if sorted(stroke_indices) != list(range(1, 19)):
            raise ValueError("Stroke indices must be 1-18")
        return holes


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

    pass  # No requiere parámetros


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
