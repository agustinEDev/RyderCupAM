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
    salida, hasta dos codos y el centro del green. Sin salida (y sin codos) es
    una muestra solo green: quien abre el mapa a mitad de hoyo (17 oct).
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
    tee: PointDTO | None = Field(
        default=None, description="La salida; null en una muestra solo green (sin codos)"
    )
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
    tee: PointDTO | None = None
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
    hay ni de quién son. Solo para los móviles de antes del 17 oct: los de ahora
    leen el hoyo entero.
    """

    tee_color: TeeColor
    tee_gender: Gender | None
    first_sample: HoleSampleDTO = Field(description="La muestra completa más antigua de esta barra")
    collecting: bool = Field(description="El del hoyo: las tres son por hoyo desde el 17 oct")


class HoleSampleStatusDTO(BaseModel):
    """
    Un hoyo: su primera muestra completa, el green de su primera muestra solo
    green y si recoge (17 oct: una referencia por hoyo). Nunca cuántas hay ni de
    quién son.
    """

    hole_number: int
    first_sample: HoleSampleDTO | None = Field(
        description="La muestra completa más antigua del hoyo, de la barra que sea"
    )
    first_green: PointDTO | None = Field(
        description=(
            "El green de la muestra solo green más antigua: quien esté en la salida "
            "completa el hoyo con él"
        )
    )
    collecting: bool = Field(
        description=(
            "True mientras el hoyo admite más muestras: menos de tres, y no lo trae "
            "con línea y green el mapa de OSM aprobado"
        )
    )
    tees: list[TeeSamplesDTO] = Field(
        description=(
            "Obsoleto (móviles de antes del 17 oct): las barras con alguna muestra "
            "completa, en el orden de su primera"
        )
    )


class SubmitHoleSampleResponseDTO(BaseModel):
    """
    Respuesta de mandar una muestra: vacía a propósito. Es la misma se guarde o no,
    para que quien la manda nunca note la diferencia (la ruta responde 204).
    """


class ListHoleSamplesResponseDTO(BaseModel):
    """Los 18 hoyos de un campo, del 1 al 18."""

    holes: list[HoleSampleStatusDTO]
