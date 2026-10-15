"""DTOs de las marcas de hoyo que hace un jugador (BE #532, PR C)."""

from pydantic import BaseModel, ConfigDict, Field

from src.modules.golf_course.application.dtos.hole_map_dtos import UtcDatetime
from src.modules.golf_course.domain.entities.hole_mark import MAX_BENDS


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
    la salida y hasta dos codos.
    """

    model_config = ConfigDict(extra="forbid")

    tee: PointDTO | None = None
    bends: list[PointDTO] = Field(default_factory=list, max_length=MAX_BENDS)
    green_center: PointDTO


class SaveHoleMarkRequestDTO(BaseModel):
    """Un jugador marca (o vuelve a marcar) un hoyo de un campo."""

    golf_course_id: str
    hole_number: int
    user_id: str
    tee: PointDTO | None = None
    bends: list[PointDTO] = Field(default_factory=list)
    green_center: PointDTO


class ListMyHoleMarksRequestDTO(BaseModel):
    """Las marcas de un jugador en un campo."""

    golf_course_id: str
    user_id: str


class HoleMarkDTO(BaseModel):
    """La marca de un hoyo, como la guardó el jugador."""

    hole_number: int
    tee: PointDTO | None = Field(
        description="Null si el hoyo ya tenía salida: solo se marcó el green"
    )
    bends: list[PointDTO]
    green_center: PointDTO
    marked_at: UtcDatetime
