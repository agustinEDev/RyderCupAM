"""DTOs del mapa de hoyos: lo que ve el jugador y lo que revisa el admin (BE #532)."""

from datetime import UTC, datetime
from typing import Annotated

from geojson_pydantic import FeatureCollection
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _utc_z(moment: datetime) -> str:
    """En UTC y con «Z»: sin zona, un navegador la tomaría por hora local."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment.isoformat() + "Z"


# Las fechas del mapa se guardan en UTC sin zona; al JSON salen con «Z»
UtcDatetime = Annotated[datetime, PlainSerializer(_utc_z, return_type=str, when_used="json")]


class HoleMapDTO(BaseModel):
    """
    El mapa de un recorrido.

    `geojson` lleva, por hoyo, su línea de juego y su green (tres puntos y, si
    lo hay, el contorno), con las coordenadas en el orden de GeoJSON:
    [longitud, latitud]. `version` es la fecha de importación: la que manda el
    admin al aprobar, para no aprobar algo que no ha visto.
    """

    golf_course_id: str
    status: str
    version: str = Field(
        description=(
            "Versión del mapa: un texto opaco. Para aprobar o rechazar se devuelve TAL "
            "CUAL se recibió (no es para interpretarlo como fecha)"
        )
    )
    attribution: str | None = None
    holes_needing_green: list[int] = Field(default_factory=list)
    geojson: FeatureCollection


class HoleMapReviewDTO(HoleMapDTO):
    """El mapa con lo que necesita el admin para revisarlo."""

    osm_reference: str
    reviewed_by: str | None = None
    reviewed_at: UtcDatetime | None = None
    rejection_reason: str | None = None


class PendingHoleMapDTO(BaseModel):
    """Un mapa pendiente en la lista del admin."""

    golf_course_id: str
    golf_course_name: str
    holes: int
    holes_needing_green: int
    imported_at: UtcDatetime
    version: str = Field(description="La versión que hay que devolver para revisarlo")
    osm_reference: str


def version_of(imported_at: datetime) -> str:
    """La versión de un mapa: su fecha de importación como texto (UTC, con µs)."""
    return _utc_z(imported_at)


class GetHoleMapRequestDTO(BaseModel):
    """El mapa de un campo."""

    golf_course_id: str


class ListPendingHoleMapsRequestDTO(BaseModel):
    """Los mapas pendientes de revisión (sin filtros)."""


class ApproveHoleMapBodyDTO(BaseModel):
    """Cuerpo de aprobar: solo la versión vista (un motivo no se acepta)."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(description="La `version` del mapa, tal cual se recibió")


class RejectHoleMapBodyDTO(ApproveHoleMapBodyDTO):
    """Cuerpo de rechazar: la versión vista y un motivo opcional (500 caracteres como mucho)."""

    reason: str | None = None


class ReviewHoleMapRequestDTO(BaseModel):
    """Aprobar o rechazar, por un admin, la versión que tiene delante."""

    golf_course_id: str
    reviewer_id: str
    version: str
    reason: str | None = None
