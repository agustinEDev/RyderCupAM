"""
Cliente de OSM que lee un fichero local en vez de Overpass (BE #532).

LO QUE NO RECUPERA: un contorno que sea una relación que osmium no sabe montar
(anillos abiertos o que se tocan) no sale en el fichero, y aquí no hay forma de
saberlo; con Overpass se reconstruía. Y las relaciones que no son multipolígono
(`type=site`) tampoco. Para un campo que falte, se puede pasar ese solo por
Overpass (`--course <id>` sin `--osm-file`).

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
MIN_RING_POINTS = 4  # un anillo cerrado: el último punto repite el primero


def _geometry(points: list[list[float]]) -> list[dict[str, float]]:
    """De `[[lon, lat], ...]` a la geometría de Overpass: `[{lat, lon}, ...]`."""
    return [{"lat": lat, "lon": lon} for lon, lat in points]


def _is_ring(points: list[list[float]]) -> bool:
    return len(points) >= MIN_RING_POINTS and points[0] == points[-1]


def _ring_way_ids(features: list[dict[str, Any]]) -> set[int]:
    """Las vías de contorno o green que vienen también como línea cerrada."""
    ids: set[int] = set()
    for feature in features:
        try:
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            if (
                properties.get("@type") == "way"
                and isinstance(properties.get("@id"), int)
                and geometry.get("type") == "LineString"
                and (
                    properties.get("leisure") == "golf_course" or properties.get("golf") == "green"
                )
                and _is_ring(geometry.get("coordinates") or [])
            ):
                ids.add(properties["@id"])
        except (AttributeError, TypeError):
            continue  # un objeto mal formado: lo descarta también la conversión
    return ids


def _way(
    osm_id: Any, tags: dict[str, Any], shape: str | None, coordinates: list, ring_ways: set[int]
) -> dict[str, Any] | None:
    """Una vía: hoyo (línea), o contorno o green (su anillo)."""
    is_area = tags.get("leisure") == "golf_course" or tags.get("golf") == "green"
    ring = None
    if shape == "LineString":
        # De un contorno o un green vale la vía tal cual, como la da Overpass:
        # osmium no da área de un anillo que se cruza, y el emparejado lo repara
        if tags.get("golf") == "hole":
            return {"type": "way", "id": osm_id, "tags": tags, "geometry": _geometry(coordinates)}
        if is_area and _is_ring(coordinates):
            ring = coordinates
    elif shape == "MultiPolygon" and coordinates and is_area and osm_id not in ring_ways:
        # Solo si no vino como línea: las vías con area=yes salen SOLO como área
        ring = coordinates[0][0]
    if ring is None:
        return None
    return {"type": "way", "id": osm_id, "tags": tags, "geometry": _geometry(ring)}


def _element(feature: dict[str, Any], ring_ways: set[int]) -> dict[str, Any] | None:
    """El elemento al estilo Overpass, o None si no es contorno, hoyo ni green."""
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    # Un id que no sea entero lo descarta parse_area, como con Overpass
    kind, osm_id = properties.get("@type"), properties.get("@id")
    tags = {k: v for k, v in properties.items() if not k.startswith("@")}
    shape = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    is_course = tags.get("leisure") == "golf_course"

    if kind == "way":
        return _way(osm_id, tags, shape, coordinates, ring_ways)
    if kind == "relation" and is_course and shape == "MultiPolygon":
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
        features: list[dict[str, Any]] = []
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as e:
            raise ValueError(
                f"{path} is not text: pass the .geojsonseq from `osmium export`, not the .pbf"
            ) from e
        for number, line in enumerate(lines, start=1):
            text = line.strip().lstrip(RECORD_SEPARATOR)
            if not text:
                continue
            try:
                feature = json.loads(text)
            except ValueError:
                logger.warning("OSM file line %d is not a readable object; skipped", number)
                continue
            if isinstance(feature, dict):
                features.append(feature)
        ring_ways = _ring_way_ids(features)
        for feature in features:
            try:
                element = _element(feature, ring_ways)
                if element is not None:
                    self._elements.append((_bounds(element), element))
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                logger.warning("OSM object %r is not usable; skipped", str(feature)[:120])
        if not self._elements:
            raise ValueError(
                f"{path} has no golf course, hole or green: build it with "
                "`osmium export … -f geojsonseq --attributes=type,id` (see the import script)"
            )

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
