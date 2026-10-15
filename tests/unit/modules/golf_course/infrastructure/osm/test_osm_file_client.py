"""
Tests del cliente que lee OSM de un fichero local en vez de Overpass (BE #532).

El fichero es el que produce `osmium export -f geojsonseq --attributes=type,id`
sobre el volcado de Geofabrik filtrado: rápido, sin límites de uso y repetible.
"""

import json
from pathlib import Path

import pytest

from src.modules.golf_course.application.ports.osm_hole_map_source import CardHole
from src.modules.golf_course.infrastructure.osm.osm_file_client import OsmFileClient
from src.modules.golf_course.infrastructure.osm.osm_hole_map_source import OsmHoleMapSource

VALDERRAMA = Path(__file__).resolve().parents[5] / "fixtures" / "osm" / "valderrama.geojsonseq"
LAT, LON = 36.28, -5.33


def _feature(tipo, id_, geometry, **tags):
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {"@type": tipo, "@id": id_, **tags},
    }


def _anillo(lat, lon, d=0.001):
    return [[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]


def _fichero(tmp_path, features, *, basura=False):
    path = tmp_path / "golf.geojsonseq"
    lineas = [json.dumps(f) for f in features]
    if basura:
        lineas.insert(1, "{esto no es json")
    # osmium separa cada objeto con RS (0x1e) en geojsonseq
    path.write_text("".join(f"\x1e{linea}\n" for linea in lineas))
    return path


CONTORNO_VIA = _feature(
    "way",
    11,
    {"type": "MultiPolygon", "coordinates": [[_anillo(LAT, LON, 0.01)]]},
    leisure="golf_course",
)
CONTORNO_RELACION = _feature(
    "relation",
    22,
    {
        "type": "MultiPolygon",
        "coordinates": [[_anillo(LAT, LON, 0.02), _anillo(LAT + 0.005, LON + 0.005, 0.002)]],
    },
    leisure="golf_course",
    type="multipolygon",
)
HOYO = _feature(
    "way",
    33,
    {"type": "LineString", "coordinates": [[LON + 0.001, LAT + 0.001], [LON + 0.002, LAT + 0.004]]},
    golf="hole",
    ref="1",
    par="4",
)
GREEN = _feature(
    "way",
    44,
    {"type": "MultiPolygon", "coordinates": [[_anillo(LAT + 0.004, LON + 0.002, 0.0002)]]},
    golf="green",
)


@pytest.mark.asyncio
async def test_f1_reads_outlines_holes_and_greens(tmp_path):
    """
    GIVEN: Un fichero con un contorno (vía), un hoyo y un green
    WHEN: Se pide la zona de un campo
    THEN: Salen los tres, con sus puntos (lat, lon) y etiquetas
    """
    client = OsmFileClient(_fichero(tmp_path, [CONTORNO_VIA, HOYO, GREEN]))

    area = await client.fetch_area(LAT, LON)

    (way,) = area.course_ways
    assert way.id == 11
    assert way.points[0] == (LAT, LON)
    assert way.points[0] == way.points[-1]
    (hole,) = area.holes
    assert (hole.id, hole.tags["ref"], hole.tags["par"]) == (33, "1", "4")
    assert hole.points[0] == (LAT + 0.001, LON + 0.001)
    (green,) = area.greens
    assert green.id == 44


@pytest.mark.asyncio
async def test_f2_only_what_is_within_2_5_km(tmp_path):
    """
    GIVEN: Un hoyo junto al campo y otro a 5 km
    WHEN: Se pide la zona del campo
    THEN: Solo sale el cercano
    """
    lejos = _feature(
        "way",
        55,
        {"type": "LineString", "coordinates": [[LON, LAT + 0.045], [LON, LAT + 0.046]]},
        golf="hole",
        ref="2",
    )
    client = OsmFileClient(_fichero(tmp_path, [HOYO, lejos]))

    area = await client.fetch_area(LAT, LON)

    assert [h.id for h in area.holes] == [33]


@pytest.mark.asyncio
async def test_f3_ignores_everything_else(tmp_path, caplog):
    """
    GIVEN: Banderas, bunkers, salidas sueltas y la copia en línea de un green
    WHEN: Se pide la zona
    THEN: No sale nada de eso, y se descarta por regla, no por ilegible
    """
    ruido = [
        _feature("node", 1, {"type": "Point", "coordinates": [LON, LAT]}, golf="pin"),
        _feature("node", 2, {"type": "Point", "coordinates": [LON, LAT]}, golf="tee"),
        _feature(
            "way", 3, {"type": "MultiPolygon", "coordinates": [[_anillo(LAT, LON)]]}, golf="bunker"
        ),
        _feature("way", 44, {"type": "LineString", "coordinates": _anillo(LAT, LON)}, golf="green"),
        _feature(
            "way",
            11,
            {"type": "LineString", "coordinates": _anillo(LAT, LON)},
            leisure="golf_course",
        ),
    ]
    client = OsmFileClient(_fichero(tmp_path, ruido))

    area = await client.fetch_area(LAT, LON)

    assert (area.course_ways, area.course_relations, area.holes, area.greens) == ((), (), (), ())
    assert not [r for r in caplog.records if "not a readable object" in r.getMessage()]


@pytest.mark.asyncio
async def test_f4_relation_comes_with_outer_and_inner_rings(tmp_path):
    """
    GIVEN: Un contorno que es una relación con un hueco
    WHEN: Se pide la zona
    THEN: Sale como relación, con su anillo exterior y su interior
    """
    client = OsmFileClient(_fichero(tmp_path, [CONTORNO_RELACION]))

    area = await client.fetch_area(LAT, LON)

    (relation,) = area.course_relations
    assert relation.id == 22
    assert len(relation.outer) == 1
    assert len(relation.inner) == 1
    assert relation.outer[0][0] == (LAT, LON)


def test_f5_missing_file_fails_at_start(tmp_path):
    """
    GIVEN: Un fichero que no existe
    WHEN: Se crea el cliente
    THEN: Error claro al arrancar, no a mitad de la pasada
    """
    with pytest.raises(FileNotFoundError):
        OsmFileClient(tmp_path / "no-esta.geojsonseq")


@pytest.mark.asyncio
async def test_f5_unreadable_line_is_skipped(tmp_path):
    """
    GIVEN: Un fichero con una línea que no es JSON entre dos buenas
    WHEN: Se pide la zona
    THEN: Se salta y lo demás se lee
    """
    client = OsmFileClient(_fichero(tmp_path, [CONTORNO_VIA, HOYO], basura=True))

    area = await client.fetch_area(LAT, LON)

    assert len(area.course_ways) == 1
    assert len(area.holes) == 1


@pytest.mark.asyncio
async def test_f7_real_valderrama_gets_its_18_holes_with_greens():
    """
    GIVEN: El fragmento real de Valderrama del volcado de OSM
    WHEN: Se empareja con su tarjeta, como con Overpass
    THEN: Sus 18 hoyos, cada uno con green (lo mismo que dio Overpass)
    """
    # La tarjeta real de Valderrama (número, par, hándicap)
    tarjeta = [
        (1, 4, 11),
        (2, 4, 7),
        (3, 3, 17),
        (4, 5, 3),
        (5, 4, 13),
        (6, 3, 15),
        (7, 4, 1),
        (8, 4, 9),
        (9, 4, 5),
        (10, 4, 18),
        (11, 5, 8),
        (12, 3, 2),
        (13, 4, 16),
        (14, 4, 12),
        (15, 3, 14),
        (16, 4, 6),
        (17, 5, 10),
        (18, 4, 4),
    ]
    card = [CardHole(number=n, par=p, stroke_index=si) for n, p, si in tarjeta]
    source = OsmHoleMapSource(OsmFileClient(VALDERRAMA))

    candidate = await source.find(
        latitude=36.28308, longitude=-5.32737, card=card, physical_holes=18
    )

    assert candidate is not None
    assert candidate.osm_reference == "way/237391513"
    assert [h.number for h in candidate.holes] == list(range(1, 19))
    assert all(h.green is not None for h in candidate.holes)
