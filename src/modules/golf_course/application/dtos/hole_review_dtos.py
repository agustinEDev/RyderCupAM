"""DTOs de lo que lee el admin para revisar los hoyos (BE #575, 17 oct 2026)."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.golf_course.application.dtos.hole_sample_dtos import HoleSampleDTO, PointDTO
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender


class HoleReviewCountDTO(BaseModel):
    """Un hoyo pendiente: cuántas muestras tiene."""

    hole_number: int
    samples: int
    # Desde el 17 oct un hoyo guardado no está pendiente: siempre false. Se
    # queda para no romper el contrato del frontend en producción
    saved: bool


class HoleReviewSummaryDTO(BaseModel):
    """Un campo con hoyos por revisar, en la lista del admin."""

    golf_course_id: str
    name: str
    holes: list[HoleReviewCountDTO] = Field(description="Solo los hoyos con muestras o línea")


class ListHoleReviewsRequestDTO(BaseModel):
    """La lista de campos con hoyos por revisar: no pide nada."""


class ListHoleReviewsResponseDTO(BaseModel):
    """Los campos con hoyos por revisar, por nombre."""

    courses: list[HoleReviewSummaryDTO]


class GetHoleReviewRequestDTO(BaseModel):
    """Revisar los hoyos de un campo."""

    golf_course_id: str


class AdminHoleSampleDTO(BaseModel):
    """
    Una muestra, para el admin: su id (para borrarla), la barra desde la que se
    jugó y sus puntos. Nunca de quién es: no se guarda.
    """

    id: UUID
    tee_color: TeeColor
    tee_gender: Gender | None
    tee: PointDTO | None = Field(description="null en una muestra solo green")
    bends: list[PointDTO]
    green_center: PointDTO
    received_on: date


class TeeMetresDTO(BaseModel):
    """Lo que dice la tarjeta de una barra en ese hoyo, para comparar con la línea."""

    tee_color: TeeColor
    tee_gender: Gender | None
    identifier: str | None
    par: int
    meters: int | None


class HoleReviewHoleDTO(BaseModel):
    """Un hoyo para revisar: la línea guardada, todas sus muestras y los metros de cada barra."""

    hole_number: int
    saved_line: HoleSampleDTO | None
    samples: list[AdminHoleSampleDTO] = Field(description="En orden de llegada")
    tees: list[TeeMetresDTO]


class HoleReviewDTO(BaseModel):
    """Los 18 hoyos de un campo, para revisarlos."""

    golf_course_id: str
    name: str
    holes: list[HoleReviewHoleDTO]
