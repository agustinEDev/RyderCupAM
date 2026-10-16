"""DTOs de las muestras anónimas de hoyo (BE #532, 16 oct 2026)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender

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
    """
    Cuerpo de mandar una muestra: su id, la barra desde la que se jugó, la
    salida, hasta dos codos y el centro del green.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(
        description=(
            "Lo genera el móvil, uno por muestra: un reenvío con el mismo id cuenta una "
            "vez. No dice nada de quién la manda"
        )
    )
    tee_color: TeeColor
    # Obligatorio aunque admita null: una barra sin género se dice, no se supone
    tee_gender: Gender | None = Field(description="MALE, FEMALE, o null si la barra no tiene")
    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list, max_length=MAX_BENDS_IN_BODY)
    green_center: PointDTO


class SubmitHoleSampleRequestDTO(BaseModel):
    """
    Una muestra de un hoyo de un campo. `user_id` solo sirve para la ventana de
    10 minutos por jugador, que vive en memoria: no se guarda con la muestra.
    """

    id: UUID
    golf_course_id: str
    hole_number: int
    user_id: str
    tee_color: TeeColor
    tee_gender: Gender | None
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


class TeeSamplesDTO(BaseModel):
    """
    Lo que se sabe de una barra de un hoyo. A propósito no dice cuántas muestras
    hay ni de quién son.
    """

    tee_color: TeeColor
    tee_gender: Gender | None
    first_sample: HoleSampleDTO = Field(description="La muestra más antigua de esta barra")
    collecting: bool = Field(description="True mientras la barra admite más muestras")


class HoleSampleStatusDTO(BaseModel):
    """Un hoyo: sus barras con alguna muestra, por orden de su primera muestra."""

    hole_number: int
    tees: list[TeeSamplesDTO] = Field(
        description=(
            "Solo las barras con alguna muestra, de la que la tuvo antes a la que la "
            "tuvo después. Una barra que no sale recoge y no tiene muestra"
        )
    )
