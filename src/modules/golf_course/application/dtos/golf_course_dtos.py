"""
Golf Course DTOs - Request/Response for use cases.
"""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor

# ============================================================================
# Nested DTOs (Tee, Hole)
# ============================================================================


class HoleDTO(BaseModel):
    """DTO para representar un hoyo."""

    hole_number: int = Field(..., ge=1, le=18, description="Número de hoyo (1-18)")
    par: int = Field(..., ge=3, le=6, description="Par del hoyo (3-6)")
    stroke_index: int = Field(..., ge=1, le=18, description="Índice de dificultad (1-18)")
    meters: int | None = Field(
        None, ge=20, le=700, description="Distancia desde esta salida, en metros"
    )

    class Config:
        from_attributes = True


class LocationDTO(BaseModel):
    """
    DTO para la ubicación de un campo.

    Todo es opcional, pero latitud y longitud van juntas: la regla la hace
    cumplir el dominio, y se comprueba también aquí para que el error salga
    como fallo de validación del campo concreto.
    """

    latitude: float | None = Field(None, ge=-90.0, le=90.0, description="Latitud en grados")
    longitude: float | None = Field(None, ge=-180.0, le=180.0, description="Longitud en grados")
    address: str | None = Field(None, max_length=300, description="Dirección postal completa")
    city: str | None = Field(None, max_length=100, description="Localidad")
    province: str | None = Field(None, max_length=100, description="Provincia o región")

    @model_validator(mode="after")
    def check_coordinates_together(self) -> "LocationDTO":
        """Media coordenada no sitúa nada en un mapa."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self

    class Config:
        from_attributes = True


class ProvenanceDTO(BaseModel):
    """
    DTO de solo lectura con la procedencia de los datos de un campo.

    No se acepta en las peticiones de alta ni de edición a propósito: la sella
    el importador, y un cliente no puede declarar que sus datos los avala una
    federación.
    """

    source: CourseSource = Field(..., description="Origen de los datos (MANUAL, RFEG, ...)")
    external_id: str | None = Field(None, description="Identificador en la fuente externa")
    imported_at: datetime | None = Field(None, description="Cuándo se importó")

    class Config:
        from_attributes = True


class TeeDTO(BaseModel):
    """DTO para representar un tee (salida)."""

    tee_gender: str | None = Field(None, description="Género del tee (MALE/FEMALE/null)")
    color: TeeColor = Field(
        TeeColor.OTHER,
        description="Color de las barras. Junto al género identifica la salida",
    )
    identifier: str | None = Field(
        None,
        max_length=50,
        description="Nombre libre opcional. Obligatorio si el color es OTHER",
    )
    # Los rangos son los absolutos de todos los tipos de campo. El rango
    # estricto que corresponde a cada tipo lo aplica el dominio: acotarlo aquí
    # impediría dar de alta pitch & putt, que WHS no valora en la misma escala.
    course_rating: float = Field(..., ge=45.0, le=90.0, description="Course Rating WHS")
    slope_rating: int = Field(..., ge=40, le=160, description="Slope Rating WHS")
    holes: list[HoleDTO] | None = Field(
        None,
        min_length=18,
        max_length=18,
        description=(
            "Tarjeta propia de esta salida. Si se omite, hereda la del campo. "
            "Necesaria cuando el par, la dificultad o las distancias cambian entre barras"
        ),
    )

    @model_validator(mode="after")
    def check_color_and_identifier(self) -> "TeeDTO":
        """
        Una salida sin color reconocible necesita nombre.

        La regla vive en el dominio, que es quien la hace cumplir. Se comprueba
        también aquí para que el error salga como un fallo de validación del
        campo concreto, y no como un rechazo genérico de la petición: omitir
        ambos valores da OTHER sin identificador, que es la combinación que el
        agregado no admite.
        """
        if self.color is TeeColor.OTHER and not (self.identifier or "").strip():
            raise ValueError(
                "identifier is required when color is OTHER (or set an explicit color)"
            )
        return self

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
    tees: list[TeeDTO] = Field(..., min_length=1, max_length=14, description="1-14 salidas")
    holes: list[HoleDTO] = Field(
        ..., min_length=18, max_length=18, description="Exactamente 18 hoyos"
    )
    location: LocationDTO | None = Field(
        None, description="Ubicación del campo. Opcional: sin ella el campo no sale por cercanía"
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
    """
    Request para listar campos aprobados (todos los usuarios).

    `limit` es opcional a propósito: sin él se devuelven todos, como siempre.
    Un cliente que no pagine no debe dejar de ver campos por un cambio del
    servidor. Los que sí paginan lo piden.

    Las coordenadas van juntas o no van: media coordenada no sitúa nada, así
    que se rechaza en el validador en lugar de ordenar por una distancia falsa.
    """

    country_code: str | None = Field(None, description="Filtrar por código ISO de país")
    name: str | None = Field(
        None, min_length=1, max_length=200, description="Filtrar por nombre parcial"
    )
    limit: int | None = Field(None, ge=1, le=100, description="Número máximo de campos")
    offset: int = Field(0, ge=0, description="Campos a saltar")
    latitude: float | None = Field(None, ge=-90, le=90, description="Latitud del dispositivo")
    longitude: float | None = Field(None, ge=-180, le=180, description="Longitud del dispositivo")
    radius_km: float | None = Field(
        None, gt=0, le=20000, description="Distancia máxima en kilómetros"
    )

    @model_validator(mode="after")
    def check_coordinates(self) -> "ListApprovedGolfCoursesRequestDTO":
        """Comprueba que las coordenadas vienen completas y que el radio tiene desde dónde medir."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.radius_km is not None and self.latitude is None:
            raise ValueError("radius_km requires latitude and longitude")
        return self

    @property
    def has_position(self) -> bool:
        """True si la petición trae una posición desde la que medir distancias."""
        return self.latitude is not None and self.longitude is not None


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
    location: LocationDTO | None = Field(None, description="Ubicación del campo, si se conoce")

    class Config:
        from_attributes = True


class GolfCourseSummaryDTO(BaseModel):
    """
    Un campo tal como aparece en un listado.

    Es el mismo campo que `GolfCourseResponseDTO` sin la tarjeta: un listado no
    la pinta, y con 802 campos son 14.436 hoyos que viajan para nada. Quien
    necesite la tarjeta pide el campo por su id.

    Las salidas sí se quedan, aunque también pesen: el panel de administración
    dibuja una insignia por cada una, y el frontend valida sus ratings al
    construir la entidad, así que recortarlas rompe en vez de degradar.
    """

    id: str = Field(..., description="ID del campo (UUID)")
    name: str = Field(..., description="Nombre del campo")
    country_code: str = Field(..., description="Código ISO del país")
    course_type: str = Field(..., description="Tipo de campo")
    creator_id: str = Field(..., description="ID del creador (UUID)")
    tees: list[TeeDTO] = Field(..., description="Lista de salidas, sin sus tarjetas")
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
    location: LocationDTO | None = Field(None, description="Ubicación del campo, si se conoce")
    distance_km: float | None = Field(
        None, description="Distancia a la posición consultada, si se pidió por cercanía"
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
    """
    Response al listar campos aprobados.

    `count` son los campos devueltos y `total` los que cumplen el filtro. Sin
    paginar coinciden; paginando, `total` es lo que necesita el cliente para
    saber si hay más. Se mantienen los dos porque `count` ya estaba publicado.
    """

    golf_courses: list[GolfCourseSummaryDTO] = Field(..., description="Lista de campos aprobados")
    count: int = Field(..., description="Número de campos devueltos en esta página")
    total: int = Field(..., description="Número de campos que cumplen el filtro")


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
    tees: list[TeeDTO] = Field(..., min_length=1, max_length=14, description="1-14 salidas")
    holes: list[HoleDTO] = Field(
        ..., min_length=18, max_length=18, description="Exactamente 18 hoyos"
    )
    # La ubicación se reemplaza entera, igual que `tees` y `holes` en esta misma
    # petición: lo que no venga dentro del objeto queda a null. No es un parcheo
    # campo a campo, así que un cliente que mande solo la localidad borra las
    # coordenadas. Omitir el objeto es lo único que conserva lo guardado.
    location: LocationDTO | None = Field(
        None,
        description=(
            "Nueva ubicación, que REEMPLAZA la actual por completo: los campos "
            "que no se envíen quedan vacíos. Omitir este objeto conserva la "
            "ubicación guardada; enviarlo vacío o con todos sus valores a null "
            "la borra"
        ),
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
