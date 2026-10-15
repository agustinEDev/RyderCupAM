"""
Cliente de OSM que lee un fichero local en vez de Overpass (BE #532).

Para las pasadas de muchos campos: Overpass es un servicio público, se satura a
menudo y limita el uso, y 800 campos llevaban unas diez horas. Con el volcado
de Geofabrik filtrado en local, la pasada entera son segundos y no falla.

El fichero es el que produce `osmium export -f geojsonseq --attributes=type,id`
(ver `scripts/import_hole_maps.py`). Cada línea es un objeto de OSM en GeoJSON,
con `[longitud, latitud]`. Se lee una vez al crear el cliente y se traduce a
los mismos elementos que daría Overpass, así que el emparejado no cambia. Los
datos de OSM van bajo licencia ODbL.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any

from .overpass_client import SEARCH_RADIUS_M, OsmArea, parse_area

logger = logging.getLogger(__name__)

METERS_PER_DEGREE = 111_320.0
RECORD_SEPARATOR = "\x1e"  # osmium separa los objetos de geojsonseq con RS


def _geometry(points: list[list[float]]) -> list[dict[str, float]]:
    """De `[[lon, lat], ...]` a la geometría de Overpass: `[{lat, lon}, ...]`."""
    return [{"lat": lat, "lon": lon} for lon, lat in points]


def _element(feature: dict[str, Any]) -> dict[str, Any] | None:
    """El elemento al estilo Overpass, o None si no es contorno, hoyo ni green."""
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    # Un id que no sea entero lo descarta parse_area, como con Overpass
    kind, osm_id = properties.get("@type"), properties.get("@id")
    tags = {k: v for k, v in properties.items() if not k.startswith("@")}
    shape = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    is_course = tags.get("leisure") == "golf_course"
    golf = tags.get("golf")

    # osmium exporta cada vía cerrada dos veces: como línea y como área. De los
    # contornos y los greens vale el área; de los hoyos, la línea
    if kind == "way" and shape == "LineString" and golf == "hole":
        return {"type": "way", "id": osm_id, "tags": tags, "geometry": _geometry(coordinates)}
    if shape != "MultiPolygon" or not coordinates:
        return None
    if kind == "way" and (is_course or golf == "green"):
        outer = coordinates[0][0]
        return {"type": "way", "id": osm_id, "tags": tags, "geometry": _geometry(outer)}
    if kind == "relation" and is_course:
        members = [
            {"type": "way", "role": "outer" if index == 0 else "inner", "geometry": _geometry(ring)}
            for polygon in coordinates
            for index, ring in enumerate(polygon)
        ]
        return {"type": "relation", "id": osm_id, "tags": tags, "members": members}
    return None


def _bounds(element: dict[str, Any]) -> tuple[float, float, float, float]:
    points = element.get("geometry") or [
        point for member in element.get("members", []) for point in member["geometry"]
    ]
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    return min(lats), max(lats), min(lons), max(lons)


class OsmFileClient:
    """Da la zona de un campo a partir del fichero de OSM filtrado."""

    def __init__(self, path: Path | str, radius_m: int = SEARCH_RADIUS_M) -> None:
        """
        Raises:
            FileNotFoundError: si el fichero no existe (mejor al arrancar que a mitad)
        """
        self._radius_m = radius_m
        self._elements: list[tuple[tuple[float, float, float, float], dict[str, Any]]] = []
        with Path(path).open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                text = line.strip().lstrip(RECORD_SEPARATOR)
                if not text:
                    continue
                try:
                    element = _element(json.loads(text))
                except (ValueError, TypeError, KeyError, IndexError):
                    logger.warning("OSM file line %d is not a readable object; skipped", number)
                    continue
                if element is not None:
                    self._elements.append((_bounds(element), element))

    async def fetch_area(self, latitude: float, longitude: float) -> OsmArea:
        """Lo que hay a menos del radio de esa coordenada, como lo daría Overpass."""
        dlat = self._radius_m / METERS_PER_DEGREE
        dlon = self._radius_m / (METERS_PER_DEGREE * math.cos(math.radians(latitude)))
        near = [
            element
            for (min_lat, max_lat, min_lon, max_lon), element in self._elements
            if min_lat <= latitude + dlat
            and max_lat >= latitude - dlat
            and min_lon <= longitude + dlon
            and max_lon >= longitude - dlon
        ]
        return parse_area({"elements": near})

    async def aclose(self) -> None:
        """Nada que cerrar: el fichero ya está leído."""
