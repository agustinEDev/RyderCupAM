"""
Tests del adaptador que une el cliente de Overpass y el emparejado (BE #532).
"""

import pytest

from src.modules.golf_course.application.ports.osm_hole_map_source import CardHole
from src.modules.golf_course.infrastructure.osm.osm_hole_map_source import OsmHoleMapSource

from .geometria import campo, green, hoyo, pt, zona

TARJETA = tuple(CardHole(number=n, par=4, stroke_index=n) for n in range(1, 19))


class ClienteFalso:
    def __init__(self, area):
        self.area = area
        self.pedidos: list[tuple[float, float]] = []

    async def fetch_area(self, latitude, longitude):
        self.pedidos.append((latitude, longitude))
        return self.area


@pytest.mark.asyncio
async def test_asks_the_area_around_the_course_and_matches_it():
    """
    GIVEN: Un cliente que devuelve un contorno con un hoyo
    WHEN: Se busca el mapa de un campo
    THEN: Se pide la zona de su coordenada y se empareja con su tarjeta
    """
    lat, lon = pt(500, 500)
    cliente = ClienteFalso(
        zona(
            cursos=[campo(3)],
            hoyos=[hoyo(10, "1", (500, 100), (500, 400))],
            greens=[green(20, 500, 400)],
        )
    )

    candidate = await OsmHoleMapSource(cliente).find(
        latitude=lat, longitude=lon, card=TARJETA, physical_holes=18
    )

    assert cliente.pedidos == [(lat, lon)]
    assert candidate is not None
    assert candidate.osm_reference == "way/3"
    assert [h.number for h in candidate.holes] == [1]
