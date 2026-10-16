"""DTOs de las muestras anónimas de hoyo (BE #532, 16 oct 2026)."""

from pydantic import BaseModel, ConfigDict, Field

# Para cortar en la entrada un cuerpo absurdo; la regla (dos codos) es del
# dominio, y una muestra con más se descarta en silencio
MAX_BENDS_IN_BODY = 20


class PointDTO(BaseModel):
    """
    Un punto, con nombre y no en una lista: en GeoJSON la longitud va primero y
    en el resto de la app la latitud, y un orden cambiado no daría error.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float


class HoleSampleBodyDTO(BaseModel):
    """Cuerpo de mandar una muestra: salida, hasta dos codos y centro del green."""

    model_config = ConfigDict(extra="forbid")

    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list, max_length=MAX_BENDS_IN_BODY)
    green_center: PointDTO


class SubmitHoleSampleRequestDTO(BaseModel):
    """Una muestra de un hoyo de un campo. Sin quién la manda: no se guarda."""

    golf_course_id: str
    hole_number: int
    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list)
    green_center: PointDTO


class ListHoleSamplesRequestDTO(BaseModel):
    """El estado de las muestras de los 18 hoyos de un campo."""

    golf_course_id: str


class HoleSampleDTO(BaseModel):
    """Una muestra: la salida, sus codos y el centro del green."""

    tee: PointDTO
    bends: list[PointDTO]
    green_center: PointDTO


class HoleSampleStatusDTO(BaseModel):
    """
    Lo que se sabe de un hoyo. A propósito no dice cuántas muestras hay ni de
    quién son.
    """

    hole_number: int
    first_sample: HoleSampleDTO | None = Field(
        description="La muestra más antigua del hoyo; null si aún no hay ninguna"
    )
    collecting: bool = Field(description="True mientras el hoyo admite más muestras")
