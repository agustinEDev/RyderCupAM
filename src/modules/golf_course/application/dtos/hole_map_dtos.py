"""DTOs del mapa de hoyos: lo que ve el jugador y lo que revisa el admin (BE #532)."""

from datetime import UTC, datetime
from typing import Annotated

from geojson_pydantic import FeatureCollection
from pydantic import BaseModel, Field, PlainSerializer


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
    version: UtcDatetime = Field(
        description=(
            "Versión del mapa (su fecha de importación, UTC). Para aprobar o rechazar "
            "se devuelve TAL CUAL se recibió"
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
    osm_reference: str


class ReviewHoleMapRequestDTO(BaseModel):
    """Aprobar o rechazar la versión que el admin tiene delante."""

    version: datetime = Field(description="La `version` del mapa, tal cual se recibió")
    reason: str | None = None
