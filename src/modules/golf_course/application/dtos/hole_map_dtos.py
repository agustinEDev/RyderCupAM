"""DTOs del mapa de hoyos: lo que ve el jugador y lo que revisa el admin (BE #532)."""

from datetime import datetime

from geojson_pydantic import FeatureCollection
from pydantic import BaseModel, Field


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
    version: datetime
    attribution: str | None = None
    holes_needing_green: list[int] = Field(default_factory=list)
    geojson: FeatureCollection


class HoleMapReviewDTO(HoleMapDTO):
    """El mapa con lo que necesita el admin para revisarlo."""

    osm_reference: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class PendingHoleMapDTO(BaseModel):
    """Un mapa pendiente en la lista del admin."""

    golf_course_id: str
    golf_course_name: str
    holes: int
    holes_needing_green: int
    imported_at: datetime
    osm_reference: str


class ReviewHoleMapRequestDTO(BaseModel):
    """Aprobar o rechazar la versión que el admin tiene delante."""

    version: datetime
    reason: str | None = None
