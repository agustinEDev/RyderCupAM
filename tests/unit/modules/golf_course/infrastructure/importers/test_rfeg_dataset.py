"""
Tests de la lectura del volcado de campos federados.

Incluyen una pasada sobre el fichero real que viaja en el repositorio: es la
comprobación que avisaría si alguien lo sustituye por otro que el importador no
sabe leer.
"""

import gzip
import json
from datetime import datetime

import pytest

from src.modules.golf_course.infrastructure.importers.rfeg_dataset import (
    DEFAULT_DATASET_PATH,
    RfegDatasetError,
    clubs_with_courses,
    load_dataset,
)
from src.modules.golf_course.infrastructure.importers.rfeg_mapper import map_club

IMPORTED_AT = datetime(2026, 8, 12, 12, 0, 0)

MINIMAL_DATASET = {
    "source": "https://rfegolf.es/clubes",
    "clubs": [{"rfeg_id": "915", "name": "CLUB DE PRUEBA", "courses": []}],
}


def write_dataset(tmp_path, dataset, name="dataset.json", compress=False):
    """Escribe un volcado de prueba y devuelve su ruta."""
    path = tmp_path / (name + ".gz" if compress else name)
    payload = json.dumps(dataset)
    if compress:
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        path.write_text(payload, encoding="utf-8")
    return path


# ============================================================================
# Tests: lectura
# ============================================================================


def test_reads_a_plain_json_dataset(tmp_path):
    """
    GIVEN: Un volcado sin comprimir
    WHEN: Se lee
    THEN: Se carga

    Al preparar una importación nueva es cómodo apuntar al JSON recién extraído.
    """
    path = write_dataset(tmp_path, MINIMAL_DATASET)

    assert load_dataset(path)["clubs"][0]["name"] == "CLUB DE PRUEBA"


def test_reads_a_compressed_dataset(tmp_path):
    """
    GIVEN: Un volcado comprimido, como el que viaja en el repositorio
    WHEN: Se lee
    THEN: Se carga
    """
    path = write_dataset(tmp_path, MINIMAL_DATASET, compress=True)

    assert load_dataset(path)["clubs"][0]["rfeg_id"] == "915"


# ============================================================================
# Tests: se para pronto ante un fichero equivocado
# ============================================================================


def test_a_missing_file_fails_clearly(tmp_path):
    """
    GIVEN: Una ruta que no existe
    WHEN: Se intenta leer
    THEN: Falla diciendo dónde ha mirado
    """
    with pytest.raises(RfegDatasetError, match="Dataset not found"):
        load_dataset(tmp_path / "no-existe.json")


def test_a_broken_file_fails_clearly(tmp_path):
    """
    GIVEN: Un fichero que no es JSON válido
    WHEN: Se intenta leer
    THEN: Falla explicando que no se ha podido leer
    """
    path = tmp_path / "roto.json"
    path.write_text("{esto no es json", encoding="utf-8")

    with pytest.raises(RfegDatasetError, match="Could not read"):
        load_dataset(path)


def test_a_file_that_is_not_utf8_fails_clearly(tmp_path):
    """
    GIVEN: Un fichero con bytes que no son UTF-8 válido
    WHEN: Se intenta leer
    THEN: Falla explicando que no se ha podido leer

    UnicodeDecodeError no es ni OSError ni JSONDecodeError, así que sin
    capturarlo salía en crudo en vez de como error del volcado.
    """
    path = tmp_path / "latin1.json"
    path.write_bytes(b'{"source": "https://rfegolf.es/clubes", "name": "\xf1"}')

    with pytest.raises(RfegDatasetError, match="Could not read"):
        load_dataset(path)


def test_a_compressed_file_that_is_not_utf8_fails_clearly(tmp_path):
    """
    GIVEN: Un volcado comprimido cuyo contenido no es UTF-8 válido
    WHEN: Se intenta leer
    THEN: Falla explicando que no se ha podido leer

    El camino de gzip decodifica por su cuenta, así que necesita su propia red.
    """
    path = tmp_path / "latin1.json.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b'{"source": "https://rfegolf.es/clubes", "name": "\xf1"}')

    with pytest.raises(RfegDatasetError, match="Could not read"):
        load_dataset(path)


def test_a_dataset_from_another_source_is_rejected(tmp_path):
    """
    GIVEN: Un volcado que no viene de la federación española
    WHEN: Se intenta leer
    THEN: Se rechaza antes de recorrer nada

    Evita importar cientos de campos desde un fichero equivocado y darse cuenta
    a mitad, con parte del trabajo ya hecho.
    """
    path = write_dataset(tmp_path, {**MINIMAL_DATASET, "source": "https://otra-cosa.example"})

    with pytest.raises(RfegDatasetError, match="does not look like an RFEG extraction"):
        load_dataset(path)


def test_an_empty_dataset_is_rejected(tmp_path):
    """
    GIVEN: Un volcado sin clubes
    WHEN: Se intenta leer
    THEN: Se rechaza
    """
    path = write_dataset(tmp_path, {**MINIMAL_DATASET, "clubs": []})

    with pytest.raises(RfegDatasetError, match="no clubs"):
        load_dataset(path)


def test_a_club_without_identity_is_rejected(tmp_path):
    """
    GIVEN: Un club sin id ni nombre
    WHEN: Se intenta leer
    THEN: Se rechaza, porque sin id no se puede reconocer después
    """
    path = write_dataset(tmp_path, {**MINIMAL_DATASET, "clubs": [{"courses": []}]})

    with pytest.raises(RfegDatasetError, match="no id or no name"):
        load_dataset(path)


# ============================================================================
# Tests: el volcado real del repositorio
# ============================================================================


def test_the_bundled_dataset_maps_completely():
    """
    GIVEN: El volcado que viaja en el repositorio
    WHEN: Se traducen todos sus clubes
    THEN: Salen 802 recorridos con 4.304 salidas y 77.472 hoyos, y ninguno falla

    Esta es la red que avisaría si alguien sustituye el fichero por otro que el
    importador no sabe leer, o si un cambio en el mapeo deja campos fuera. Los
    totales de salidas y hoyos son los que anuncia el CHANGELOG: contar solo
    recorridos no detectaría un volcado que llegara con las tarjetas a medias.
    """
    dataset = load_dataset(DEFAULT_DATASET_PATH)
    clubs = clubs_with_courses(dataset)

    mapped = [course for club in clubs for course in map_club(club, IMPORTED_AT)]
    tees = [tee for course in mapped for tee in course.request.tees]

    assert len(mapped) == 802
    assert len({course.provenance.external_id for course in mapped}) == 802
    assert len({course.name for course in mapped}) == 802
    assert all(course.physical_holes in (9, 18) for course in mapped)
    assert len(tees) == 4304
    assert sum(len(tee.holes) for tee in tees) == 77472
