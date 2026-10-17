"""DTOs de la línea que el admin guarda de cada hoyo (BE #575, 17 oct 2026)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    MAX_BENDS_IN_BODY,
    PointDTO,
)


class SaveHoleLineBodyDTO(BaseModel):
    """Cuerpo de guardar la línea de un hoyo: la salida, hasta dos codos y el green."""

    model_config = ConfigDict(extra="forbid")

    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list, max_length=MAX_BENDS_IN_BODY)
    green_center: PointDTO


class SaveHoleLineRequestDTO(BaseModel):
    """Guardar la línea de referencia de un hoyo de un campo."""

    golf_course_id: str
    hole_number: int
    admin_id: str
    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list)
    green_center: PointDTO


class ReopenHoleRequestDTO(BaseModel):
    """Reabrir un hoyo: se quita su línea y vuelve a recoger muestras."""

    golf_course_id: str
    hole_number: int


class DeleteHoleSampleRequestDTO(BaseModel):
    """Borrar una muestra mala de un campo: deja libre su hueco."""

    golf_course_id: str
    sample_id: UUID
