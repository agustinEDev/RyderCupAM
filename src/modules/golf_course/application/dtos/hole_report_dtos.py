"""DTOs de los reportes de hoyo (entrega 7, 18 oct 2026)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    MAX_BENDS_IN_BODY,
    PointDTO,
)
from src.modules.golf_course.domain.entities.hole_report import HoleReportReason


class HoleReportBodyDTO(BaseModel):
    """
    Cuerpo de reportar un hoyo: su id, el motivo y la línea que propone el
    jugador (salida, hasta dos codos y centro del green).
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(
        description=(
            "Lo genera el móvil, uno por reporte: un reenvío con el mismo id cuenta una "
            "vez. No dice nada de quién lo manda"
        )
    )
    reason: HoleReportReason
    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list, max_length=MAX_BENDS_IN_BODY)
    green_center: PointDTO


class SubmitHoleReportRequestDTO(BaseModel):
    """
    Un reporte de un hoyo de un campo. `user_id` solo sirve para la ventana de
    10 minutos por jugador, que vive en memoria: no se guarda con el reporte.
    """

    id: UUID
    golf_course_id: str
    hole_number: int
    user_id: str
    reason: HoleReportReason
    tee: PointDTO
    bends: list[PointDTO] = Field(default_factory=list)
    green_center: PointDTO


class SubmitHoleReportResponseDTO(BaseModel):
    """Vacío: la ruta responde 204 se guarde o no, y el jugador no nota la diferencia."""


class DiscardHoleReportRequestDTO(BaseModel):
    """El admin descarta un reporte de un campo."""

    golf_course_id: str
    report_id: UUID
