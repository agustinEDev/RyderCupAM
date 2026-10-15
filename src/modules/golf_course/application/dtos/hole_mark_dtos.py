"""DTOs de las marcas de hoyo que hace un jugador (BE #532, PR C)."""

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from src.modules.golf_course.application.dtos.hole_map_dtos import UtcDatetime

# Para cortar en la entrada un cuerpo absurdo; la regla (dos codos) es del dominio,
# que responde INVALID_HOLE_MARK con su código
MAX_BENDS_IN_BODY = 20


class PointDTO(BaseModel):
    """
    Un punto, con nombre y no en una lista: en GeoJSON la longitud va primero y
    en el resto de la app la latitud, y un orden cambiado no daría error.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float


class HoleMarkBodyDTO(BaseModel):
    """
    Cuerpo de marcar un hoyo: el centro del green y, si el hoyo no tiene salida,
    la salida y hasta dos codos (con más, INVALID_HOLE_MARK, del dominio).
    """

    model_config = ConfigDict(extra="forbid")

    tee: PointDTO | None = None
    bends: list[PointDTO] = Field(default_factory=list, max_length=MAX_BENDS_IN_BODY)
    green_center: PointDTO
    # Con zona obligatoria: una hora local sin ella se tomaría por UTC y la
    # regla de «gana la más reciente» compararía instantes equivocados
    marked_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "Cuándo marcó el jugador (con zona). La que se envía tarde desde la cola sin "
            "cobertura no pisa a una posterior. Sin él, ahora"
        ),
    )


class SaveHoleMarkRequestDTO(BaseModel):
    """Un jugador marca (o vuelve a marcar) un hoyo de un campo."""

    golf_course_id: str
    hole_number: int
    user_id: str
    tee: PointDTO | None = None
    bends: list[PointDTO] = Field(default_factory=list)
    green_center: PointDTO
    marked_at: datetime | None = None


class ListMyHoleMarksRequestDTO(BaseModel):
    """Las marcas de un jugador en un campo."""

    golf_course_id: str
    user_id: str


class HoleMarkDTO(BaseModel):
    """La marca de un hoyo, como la guardó el jugador."""

    hole_number: int
    tee: PointDTO | None = Field(
        description="Null si el hoyo ya tenía salida: solo cuenta el green"
    )
    bends: list[PointDTO]
    green_center: PointDTO
    marked_at: UtcDatetime
