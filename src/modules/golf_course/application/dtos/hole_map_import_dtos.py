"""DTOs de la importación del mapa de hoyos desde OpenStreetMap (BE #532)."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ImportHoleMapStatus(StrEnum):
    """Qué pasó (o qué pasaría, en seco) con el mapa de un campo."""

    CREATED = "CREATED"
    REIMPORTED = "REIMPORTED"
    SKIPPED_APPROVED = "SKIPPED_APPROVED"  # el mapa ya lo aprobó un admin
    NO_COORDINATES = "NO_COORDINATES"
    NO_OUTLINE = "NO_OUTLINE"  # OSM no tiene el contorno del campo cerca
    NO_VALID_HOLES = "NO_VALID_HOLES"
    OSM_UNAVAILABLE = "OSM_UNAVAILABLE"


class ImportHoleMapRequestDTO(BaseModel):
    """Importar el mapa de un campo; sin `apply`, en seco."""

    golf_course_id: str
    apply: bool = False


class ImportHoleMapResponseDTO(BaseModel):
    """Resultado de importar el mapa de un campo."""

    status: ImportHoleMapStatus
    holes_imported: int = 0
    discarded: dict[str, int] = Field(default_factory=dict)
    osm_reference: str | None = None
