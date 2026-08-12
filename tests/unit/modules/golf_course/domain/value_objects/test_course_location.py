"""
Tests del Value Object CourseLocation.

La ubicación es lo que permitirá proponer campos cercanos a la posición del
dispositivo, así que la regla que más se protege aquí es que las coordenadas
vayan completas: media coordenada no sitúa nada en un mapa.
"""

import pytest

from src.modules.golf_course.domain.value_objects.course_location import CourseLocation

# ============================================================================
# Tests: construcción básica
# ============================================================================


def test_location_can_be_empty():
    """
    GIVEN: Ningún dato de ubicación
    WHEN: Se construye el Value Object
    THEN: Es válido y se reconoce como vacío
    """
    location = CourseLocation()

    assert location.is_empty is True
    assert location.has_coordinates is False


def test_location_with_full_data():
    """
    GIVEN: Coordenadas, dirección, localidad y provincia
    WHEN: Se construye el Value Object
    THEN: Conserva todos los datos y se puede situar en un mapa
    """
    location = CourseLocation(
        latitude=43.29519,
        longitude=-2.87352,
        address="CALLE EREAGA BIDEA S/N, 48160, DERIO, VIZCAYA",
        city="DERIO",
        province="VIZCAYA",
    )

    assert location.latitude == 43.29519
    assert location.longitude == -2.87352
    assert location.city == "DERIO"
    assert location.province == "VIZCAYA"
    assert location.has_coordinates is True
    assert location.is_empty is False


def test_location_accepts_address_without_coordinates():
    """
    GIVEN: Una dirección pero ninguna coordenada
    WHEN: Se construye el Value Object
    THEN: Es válido, aunque el campo no salga en búsquedas por cercanía
    """
    location = CourseLocation(city="MARBELLA", province="MÁLAGA")

    assert location.has_coordinates is False
    assert location.is_empty is False


# ============================================================================
# Tests: coordenadas completas
# ============================================================================


def test_latitude_without_longitude_is_rejected():
    """
    GIVEN: Solo latitud
    WHEN: Se construye el Value Object
    THEN: Falla, porque media coordenada no sitúa nada
    """
    with pytest.raises(ValueError, match="both latitude and longitude"):
        CourseLocation(latitude=43.29519)


def test_longitude_without_latitude_is_rejected():
    """
    GIVEN: Solo longitud
    WHEN: Se construye el Value Object
    THEN: Falla, porque media coordenada no sitúa nada
    """
    with pytest.raises(ValueError, match="both latitude and longitude"):
        CourseLocation(longitude=-2.87352)


def test_zero_coordinates_are_valid():
    """
    GIVEN: Latitud y longitud a cero (el punto del golfo de Guinea)
    WHEN: Se construye el Value Object
    THEN: Es válido: cero es una coordenada, no un dato ausente
    """
    location = CourseLocation(latitude=0.0, longitude=0.0)

    assert location.has_coordinates is True


# ============================================================================
# Tests: rangos geográficos
# ============================================================================


@pytest.mark.parametrize("latitude", [-90.1, 90.1, 180.0])
def test_latitude_out_of_range_is_rejected(latitude):
    """
    GIVEN: Una latitud fuera de -90..90
    WHEN: Se construye el Value Object
    THEN: Falla
    """
    with pytest.raises(ValueError, match="Latitude must be between"):
        CourseLocation(latitude=latitude, longitude=0.0)


@pytest.mark.parametrize("longitude", [-180.1, 180.1, 360.0])
def test_longitude_out_of_range_is_rejected(longitude):
    """
    GIVEN: Una longitud fuera de -180..180
    WHEN: Se construye el Value Object
    THEN: Falla
    """
    with pytest.raises(ValueError, match="Longitude must be between"):
        CourseLocation(latitude=0.0, longitude=longitude)


@pytest.mark.parametrize(
    "latitude,longitude",
    [(-90.0, -180.0), (90.0, 180.0)],
)
def test_range_limits_are_accepted(latitude, longitude):
    """
    GIVEN: Coordenadas justo en los límites geográficos
    WHEN: Se construye el Value Object
    THEN: Son válidas
    """
    location = CourseLocation(latitude=latitude, longitude=longitude)

    assert location.has_coordinates is True


# ============================================================================
# Tests: normalización de texto
# ============================================================================


def test_blank_strings_become_none():
    """
    GIVEN: Textos en blanco
    WHEN: Se construye el Value Object
    THEN: Se normalizan a None, para que nadie tenga que distinguir '' de None
    """
    location = CourseLocation(address="   ", city="", province="\t")

    assert location.address is None
    assert location.city is None
    assert location.province is None
    assert location.is_empty is True


def test_text_is_trimmed():
    """
    GIVEN: Textos con espacios alrededor
    WHEN: Se construye el Value Object
    THEN: Se recortan
    """
    location = CourseLocation(city="  MARBELLA  ")

    assert location.city == "MARBELLA"


def test_address_longer_than_limit_is_rejected():
    """
    GIVEN: Una dirección de más de 300 caracteres
    WHEN: Se construye el Value Object
    THEN: Falla, porque no cabría en la columna
    """
    with pytest.raises(ValueError, match="address must be at most 300"):
        CourseLocation(address="A" * 301)


@pytest.mark.parametrize("field_name", ["city", "province"])
def test_city_and_province_longer_than_limit_are_rejected(field_name):
    """
    GIVEN: Una localidad o provincia de más de 100 caracteres
    WHEN: Se construye el Value Object
    THEN: Falla
    """
    with pytest.raises(ValueError, match=f"{field_name} must be at most 100"):
        CourseLocation(**{field_name: "A" * 101})


# ============================================================================
# Tests: igualdad
# ============================================================================


def test_two_locations_with_same_data_are_equal():
    """
    GIVEN: Dos ubicaciones con los mismos datos
    WHEN: Se comparan
    THEN: Son iguales, como corresponde a un Value Object
    """
    first = CourseLocation(latitude=36.5, longitude=-4.9, city="MARBELLA")
    second = CourseLocation(latitude=36.5, longitude=-4.9, city="MARBELLA")

    assert first == second
