"""
Cliente de Overpass, la API de lectura de OpenStreetMap (BE #532).

Pide en una sola consulta lo que hace falta para el mapa de un campo alrededor de
su coordenada (contornos de campo, hoyos y greens, con su geometría) y lo traduce
a datos propios. Los datos de OSM van bajo licencia ODbL.

Overpass es un servicio público de uso justo: limita a quien abusa (429) y a
menudo se satura (502, 503, 504, o no llega a responder). Esos se reintentan con
esperas crecientes; cualquier otro fallo, y una respuesta ilegible, llegan como
OsmUnavailableError.
"""

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.modules.golf_course.application.ports.osm_hole_map_source import OsmUnavailableError

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass pide que cada cliente se identifique con un contacto. «RCF», sin el
# nombre comercial (20 oct 2026, mientras se elige uno nuevo).
USER_AGENT = "RCF/1.0 (agustin.estevez.dominguez@gmail.com)"
SEARCH_RADIUS_M = 2500
QUERY_TIMEOUT_S = 60
# 429: límite de uso; 502/503/504: la pasarela de Overpass cargada, muy habitual
RETRY_STATUSES = frozenset({429, 502, 503, 504})
RETRY_WAITS_S = (10.0, 30.0)
# Si Overpass pide esperar más (Retry-After), se le hace caso, con un tope
MAX_RETRY_WAIT_S = 120.0
# Overpass corta una consulta larga o pesada con un 200 y esto en `remark`
RUNTIME_ERROR_MARK = "runtime error"

Point = tuple[float, float]  # (latitud, longitud)
MIN_WAY_POINTS = 2  # una vía con menos no dibuja nada


@dataclass(frozen=True)
class OsmWay:
    """Una vía de OSM: su id, sus etiquetas y sus puntos en orden."""

    id: int
    tags: Mapping[str, str]
    points: tuple[Point, ...]


@dataclass(frozen=True)
class OsmRelation:
    """Una relación multipolígono: sus trozos de anillo exterior e interior."""

    id: int
    tags: Mapping[str, str]
    outer: tuple[tuple[Point, ...], ...]
    inner: tuple[tuple[Point, ...], ...] = ()


@dataclass(frozen=True)
class OsmArea:
    """Lo que OSM tiene alrededor de un campo."""

    course_ways: tuple[OsmWay, ...] = ()
    course_relations: tuple[OsmRelation, ...] = ()
    holes: tuple[OsmWay, ...] = ()
    greens: tuple[OsmWay, ...] = field(default=())


def build_query(latitude: float, longitude: float, radius_m: int = SEARCH_RADIUS_M) -> str:
    """La consulta Overpass QL de la zona de un campo."""
    around = f"around:{radius_m},{latitude},{longitude}"
    return (
        f"[out:json][timeout:{QUERY_TIMEOUT_S}];"
        "("
        f'way["leisure"="golf_course"]({around});'
        f'relation["leisure"="golf_course"]({around});'
        f'way["golf"="hole"]({around});'
        f'way["golf"="green"]({around});'
        ");"
        "out tags geom;"
    )


def _points(geometry: Any) -> tuple[Point, ...]:
    """Los puntos de una geometría; vacío si alguno no es una coordenada de verdad."""
    if not isinstance(geometry, list):
        return ()
    points: list[Point] = []
    for node in geometry:
        try:
            lat, lon = float(node["lat"]), float(node["lon"])
        except (TypeError, KeyError, ValueError):
            return ()
        if not (math.isfinite(lat) and math.isfinite(lon)):
            return ()
        points.append((lat, lon))
    return tuple(points)


def parse_area(payload: Any) -> OsmArea:
    """
    Traduce la respuesta de Overpass; ignora lo que no se usa o no se entiende.

    Raises:
        OsmUnavailableError: si la respuesta no trae la lista de elementos
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise OsmUnavailableError("Overpass answered without a list of elements")
    remark = payload.get("remark")
    if isinstance(remark, str) and RUNTIME_ERROR_MARK in remark.lower():
        # La lista que acompaña está a medias: tomarla por buena perdería hoyos
        raise OsmUnavailableError(f"Overpass cut the query: {remark}")

    course_ways: list[OsmWay] = []
    course_relations: list[OsmRelation] = []
    holes: list[OsmWay] = []
    greens: list[OsmWay] = []
    for element in payload["elements"]:
        if not isinstance(element, dict) or not isinstance(element.get("id"), int):
            continue
        tags = element.get("tags") or {}
        if not isinstance(tags, dict):
            continue
        kind = element.get("type")
        if kind == "relation" and tags.get("leisure") == "golf_course":
            members = [m for m in element.get("members") or [] if isinstance(m, dict)]
            outer = tuple(
                # Sin rol (multipolígonos antiguos) se toma como exterior
                p
                for m in members
                if m.get("role") in ("outer", "") and (p := _points(m.get("geometry")))
            )
            inner = tuple(
                p for m in members if m.get("role") == "inner" and (p := _points(m.get("geometry")))
            )
            if outer:
                course_relations.append(
                    OsmRelation(id=element["id"], tags=tags, outer=outer, inner=inner)
                )
            continue
        if kind != "way":
            continue
        points = _points(element.get("geometry"))
        if len(points) < MIN_WAY_POINTS:
            continue
        way = OsmWay(id=element["id"], tags=tags, points=points)
        if tags.get("leisure") == "golf_course":
            course_ways.append(way)
        elif tags.get("golf") == "hole":
            holes.append(way)
        elif tags.get("golf") == "green":
            greens.append(way)

    return OsmArea(
        course_ways=tuple(course_ways),
        course_relations=tuple(course_relations),
        holes=tuple(holes),
        greens=tuple(greens),
    )


def _wait(own: float, response: httpx.Response) -> float:
    """La espera propia, o la que pida Overpass si es mayor (con un tope)."""
    try:
        asked = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return own
    return min(max(own, asked), MAX_RETRY_WAIT_S)


class OverpassClient:
    """
    Pide a Overpass la zona de un campo.

    Usa una sola conexión para toda la pasada (Overpass es un servicio de uso
    justo): quien lo crea lo cierra con `aclose()` al terminar.
    """

    def __init__(
        self,
        url: str = DEFAULT_OVERPASS_URL,
        timeout_s: float = QUERY_TIMEOUT_S + 15,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._url = url
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._http: httpx.AsyncClient | None = None

    async def aclose(self) -> None:
        """Cierra la conexión, si llegó a abrirse."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def fetch_area(self, latitude: float, longitude: float) -> OsmArea:
        """
        La zona alrededor de esa coordenada.

        Raises:
            OsmUnavailableError: si Overpass no responde o responde algo ilegible
        """
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._timeout_s)
        data = {"data": build_query(latitude, longitude)}
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        waits = list(RETRY_WAITS_S)
        while True:
            try:
                response = await self._http.post(self._url, data=data, headers=headers)
            except httpx.TransportError as e:
                # Tiempo agotado o conexión caída: lo más común con Overpass saturado
                if waits:
                    await self._sleep(waits.pop(0))
                    continue
                raise OsmUnavailableError(f"Overpass is unreachable: {e!r}") from e
            except httpx.HTTPError as e:
                raise OsmUnavailableError(f"Overpass is unreachable: {e!r}") from e
            if response.status_code in RETRY_STATUSES and waits:
                await self._sleep(_wait(waits.pop(0), response))
                continue
            if response.status_code != httpx.codes.OK:
                raise OsmUnavailableError(f"Overpass answered {response.status_code}")
            try:
                payload = response.json()
            except ValueError as e:
                raise OsmUnavailableError("Overpass answered something that is not JSON") from e
            return parse_area(payload)
