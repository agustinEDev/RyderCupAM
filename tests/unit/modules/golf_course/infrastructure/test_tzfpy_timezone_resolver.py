"""
Tests del resolutor de zonas horarias por coordenadas (BE #305).

Con datos reales de campos que hay en la base: Madrid y Canarias son el caso que
obliga a esto —mismo país, husos distintos— y Pebble Beach comprueba que no se
ha colado ningún atajo español.
"""

import pytest

from src.modules.golf_course.infrastructure.services.tzfpy_timezone_resolver import (
    TzfpyTimezoneResolver,
)


@pytest.fixture
def resolver() -> TzfpyTimezoneResolver:
    return TzfpyTimezoneResolver()


class TestForCoordinates:
    @pytest.mark.parametrize(
        ("nombre", "latitude", "longitude", "zona"),
        [
            ("Club de Campo (Madrid)", 40.4637, -3.7492, "Europe/Madrid"),
            ("Abama (Tenerife)", 28.17084, -16.7926, "Atlantic/Canary"),
            ("Golf de Derio (Bizkaia)", 43.29519, -2.87352, "Europe/Madrid"),
            ("Pebble Beach (California)", 36.5674, -121.9490, "America/Los_Angeles"),
            ("Royal Melbourne", -37.9738, 145.0246, "Australia/Melbourne"),
        ],
    )
    def test_saca_la_zona_del_punto(self, resolver, nombre, latitude, longitude, zona):
        assert resolver.for_coordinates(latitude, longitude) == zona, nombre

    def test_dos_campos_del_mismo_pais_pueden_estar_en_husos_distintos(self, resolver):
        """La razón de ser de todo esto: el país no basta."""
        peninsula = resolver.for_coordinates(40.4637, -3.7492)
        canarias = resolver.for_coordinates(28.17084, -16.7926)

        assert peninsula != canarias

    @pytest.mark.parametrize(
        ("latitude", "longitude"),
        [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
    )
    def test_unas_coordenadas_imposibles_no_revientan(self, resolver, latitude, longitude):
        """Devolver None deja el campo sin apertura automática, que es lo seguro."""
        assert resolver.for_coordinates(latitude, longitude) is None

    def test_sin_coordenadas_no_hay_zona(self, resolver):
        assert resolver.for_coordinates(None, None) is None
        assert resolver.for_coordinates(40.4637, None) is None
