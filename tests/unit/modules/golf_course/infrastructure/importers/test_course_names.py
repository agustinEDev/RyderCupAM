"""
Tests de los nombres que se generan a partir de lo que publica la RFEG.

La federación publica en mayúsculas, sin tildes y con el club delante solo a
veces. Aquí se comprueba que el resultado es legible sin dejar de ser fiel.
"""

import pytest

from src.modules.golf_course.infrastructure.importers.course_names import (
    build_club_course_names,
    build_course_name,
    normalize_for_comparison,
    prettify,
    prettify_place,
)

# ============================================================================
# Tests: capitalización y tildes
# ============================================================================


@pytest.mark.parametrize(
    "source,expected",
    [
        ("ALHAURIN", "Alhaurín"),
        ("SANTA MARIA GOLF", "Santa María Golf"),
        ("GOLF DE DERIO", "Golf de Derio"),
        ("HIERRO 3 REINO DE LEON", "Hierro 3 Reino de León"),
        ("EL PRAT", "El Prat"),
    ],
)
def test_prettify_restores_accents_and_capitalisation(source, expected):
    """
    GIVEN: Un nombre en mayúsculas y sin tildes
    WHEN: Se prepara para mostrarlo
    THEN: Queda legible y con sus tildes
    """
    assert prettify(source) == expected


@pytest.mark.parametrize("acronym", ["P&P", "R.C.I.", "RCG", "RSHECC", "A"])
def test_acronyms_stay_in_capitals(acronym):
    """
    GIVEN: Una sigla
    WHEN: Se prepara el nombre
    THEN: Se queda en mayúsculas, porque 'R.c.i.' no significa nada
    """
    assert acronym in prettify(f"CAMPO {acronym}")


def test_particles_go_lowercase_except_at_the_start():
    """
    GIVEN: Un nombre que empieza por artículo y contiene preposiciones
    WHEN: Se prepara
    THEN: El artículo inicial se mantiene y las partículas interiores bajan
    """
    assert prettify("EL CLUB DE GOLF DE LA COSTA") == "El Club de Golf de la Costa"


def test_functional_words_never_get_an_accent():
    """
    GIVEN: Un nombre con la palabra 'EL', que en el corpus aparece como 'ÉL'
    WHEN: Se prepara
    THEN: No se acentúa: es artículo, no pronombre

    Sin la lista de palabras funcionales, el cruce del corpus 'demuestra' que
    EL lleva tilde y estropea 55 nombres.
    """
    assert prettify("EL SALER") == "El Saler"


# ============================================================================
# Tests: el club solo cuando hace falta
# ============================================================================


def test_the_club_is_not_repeated_when_the_course_already_names_it():
    """
    GIVEN: Un recorrido cuyo nombre ya contiene el del club
    WHEN: Se compone el nombre final
    THEN: No se antepone el club
    """
    assert build_course_name("ALDEAMAYOR CLUB DE GOLF", "ALDEAMAYOR - P&P") == "Aldeamayor - P&P"


def test_the_club_is_added_when_the_course_does_not_name_it():
    """
    GIVEN: Un recorrido con nombre propio que no recuerda al club
    WHEN: Se compone el nombre final
    THEN: Se antepone el club, para que buscarlo por el club lo encuentre
    """
    name = build_course_name("GOLF MUNICIPAL DE GIJÓN", "LA LLOREA - Tragamón")

    assert name == "Golf Municipal de Gijón - La Llorea - Tragamón"


# ============================================================================
# Tests: nombres repetidos dentro de un club
# ============================================================================


def test_a_name_repeated_by_the_source_is_collapsed():
    """
    GIVEN: Un club cuyo único recorrido se llama igual que el club
    WHEN: Se componen los nombres
    THEN: El nombre no se dice dos veces
    """
    names = build_club_course_names("AGUILON GOLF", ["AGUILON GOLF - Aguilón Golf"])

    assert names == ["Aguilón Golf"]


def test_collapsing_is_skipped_when_it_would_confuse_two_courses():
    """
    GIVEN: Un club con dos recorridos, uno llamado 'X - X' y otro 'X'
    WHEN: Se componen los nombres
    THEN: Se conserva el largo, para que no queden indistinguibles

    Es el caso de La Envía, con un campo de par 70 y otro de par 58 nombrados
    así por la federación.
    """
    names = build_club_course_names("LA ENVIA GOLF", ["LA ENVIA - La Envía", "LA ENVIA"])

    assert names == ["La Envía - La Envía", "La Envía"]
    assert len(set(names)) == 2


def test_every_course_of_a_club_gets_a_name():
    """
    GIVEN: Un club con varios recorridos
    WHEN: Se componen los nombres
    THEN: Sale uno por recorrido, en el mismo orden
    """
    names = build_club_course_names(
        "ALDEAMAYOR CLUB DE GOLF",
        ["ALDEAMAYOR - P&P", "ALDEAMAYOR - Pares 3", "ALDEAMAYOR - R.C.I."],
    )

    assert names == ["Aldeamayor - P&P", "Aldeamayor - Pares 3", "Aldeamayor - R.C.I."]


# ============================================================================
# Tests: localidades y provincias
# ============================================================================


@pytest.mark.parametrize(
    "source,expected",
    [
        ("CALA DE MIJAS, LA", "La Cala de Mijas"),
        ("PALMAS DE GRAN CANARIA, LAS", "Las Palmas de Gran Canaria"),
        ("MALAGA", "Málaga"),
        ("CORDOBA", "Córdoba"),
        ("ZARAGOZA", "Zaragoza"),
    ],
)
def test_places_undo_the_trailing_article(source, expected):
    """
    GIVEN: Una localidad del nomenclátor oficial, con el artículo detrás
    WHEN: Se prepara para mostrarla
    THEN: El artículo vuelve a su sitio y el nombre queda legible
    """
    assert prettify_place(source) == expected


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_an_empty_place_is_none(empty):
    """
    GIVEN: Una localidad ausente o en blanco
    WHEN: Se prepara
    THEN: Devuelve None, no una cadena vacía
    """
    assert prettify_place(empty) is None


# ============================================================================
# Tests: comparación
# ============================================================================


def test_comparison_ignores_accents_case_and_punctuation():
    """
    GIVEN: El mismo nombre escrito de dos maneras
    WHEN: Se normaliza para comparar
    THEN: Coinciden
    """
    assert normalize_for_comparison("Alhaurín - P&P") == normalize_for_comparison("ALHAURIN  P P")
