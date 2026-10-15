"""Adaptador del puerto IOsmHoleMapSource: Overpass + emparejado (BE #532)."""

from collections.abc import Sequence
from typing import Protocol

from src.modules.golf_course.application.ports.osm_hole_map_source import (
    CardHole,
    IOsmHoleMapSource,
    OsmHoleMapCandidate,
)

from .hole_map_matcher import match_hole_map
from .overpass_client import OsmArea


class _AreaClient(Protocol):
    async def fetch_area(self, latitude: float, longitude: float) -> OsmArea: ...


class OsmHoleMapSource(IOsmHoleMapSource):
    """Pide a Overpass la zona del campo y la empareja con su tarjeta."""

    def __init__(self, client: _AreaClient) -> None:
        self._client = client

    async def find(
        self,
        *,
        latitude: float,
        longitude: float,
        card: Sequence[CardHole],
        physical_holes: int,
    ) -> OsmHoleMapCandidate | None:
        area = await self._client.fetch_area(latitude, longitude)
        return match_hole_map(
            area, latitude=latitude, longitude=longitude, card=card, physical_holes=physical_holes
        )
