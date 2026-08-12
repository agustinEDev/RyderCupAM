"""
Tests del Value Object CourseProvenance.

Lo que se protege aquí es la coherencia entre origen y datos de importación: un
campo tecleado por una persona no puede llevar identificador de una federación,
y uno importado sin fecha no permitiría saber si sus datos son de este año o de
hace tres.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.value_objects.course_provenance import CourseProvenance
from src.modules.golf_course.domain.value_objects.course_source import CourseSource

IMPORTED_AT = datetime(2026, 8, 12, 10, 0, 0)


# ============================================================================
# Tests: alta manual
# ============================================================================


def test_default_provenance_is_manual():
    """
    GIVEN: Ningún dato de procedencia
    WHEN: Se construye el Value Object
    THEN: El campo se considera dado de alta a mano
    """
    provenance = CourseProvenance()

    assert provenance.source is CourseSource.MANUAL
    assert provenance.is_imported is False


def test_manual_course_cannot_carry_an_external_id():
    """
    GIVEN: Un origen manual con identificador externo
    WHEN: Se construye el Value Object
    THEN: Falla, porque nadie ha importado ese campo de ninguna parte
    """
    with pytest.raises(ValueError, match="cannot have an external id"):
        CourseProvenance(source=CourseSource.MANUAL, external_id="915")


def test_manual_course_cannot_carry_an_import_date():
    """
    GIVEN: Un origen manual con fecha de importación
    WHEN: Se construye el Value Object
    THEN: Falla
    """
    with pytest.raises(ValueError, match="cannot have an import date"):
        CourseProvenance(source=CourseSource.MANUAL, imported_at=IMPORTED_AT)


# ============================================================================
# Tests: campos importados
# ============================================================================


def test_imported_course_keeps_source_and_identifiers():
    """
    GIVEN: Un campo importado de la RFEG con su identificador
    WHEN: Se construye el Value Object
    THEN: Conserva origen, identificador y fecha
    """
    provenance = CourseProvenance(
        source=CourseSource.RFEG, external_id="3727", imported_at=IMPORTED_AT
    )

    assert provenance.source is CourseSource.RFEG
    assert provenance.external_id == "3727"
    assert provenance.imported_at == IMPORTED_AT
    assert provenance.is_imported is True


def test_imported_course_may_have_no_external_id():
    """
    GIVEN: Una fuente que no publica identificador estable por recorrido
    WHEN: Se construye el Value Object sin identificador
    THEN: Es válido, porque no todas las federaciones lo publican
    """
    provenance = CourseProvenance(source=CourseSource.RFEG, imported_at=IMPORTED_AT)

    assert provenance.external_id is None
    assert provenance.is_imported is True


def test_imported_course_needs_an_import_date():
    """
    GIVEN: Un campo importado sin fecha
    WHEN: Se construye el Value Object
    THEN: Falla: sin fecha no se sabe cuándo se contrastó con la fuente
    """
    with pytest.raises(ValueError, match="needs an import date"):
        CourseProvenance(source=CourseSource.RFEG, external_id="3727")


# ============================================================================
# Tests: normalización
# ============================================================================


def test_blank_external_id_becomes_none():
    """
    GIVEN: Un identificador externo en blanco
    WHEN: Se construye el Value Object
    THEN: Se normaliza a None, para no guardar un identificador que no lo es
    """
    provenance = CourseProvenance(
        source=CourseSource.RFEG, external_id="   ", imported_at=IMPORTED_AT
    )

    assert provenance.external_id is None


def test_a_source_given_as_string_is_converted():
    """
    GIVEN: Un origen escrito como cadena, como llegaría de un fichero de datos
    WHEN: Se construye el Value Object
    THEN: Queda convertido al enum, no como texto suelto
    """
    provenance = CourseProvenance(source="RFEG", imported_at=IMPORTED_AT)

    assert provenance.source is CourseSource.RFEG


@pytest.mark.parametrize("invalid_source", ["rfeg", "FPG", "", "MANUAL_2"])
def test_an_unknown_source_is_rejected(invalid_source):
    """
    GIVEN: Un origen que no está en el enum, o el mismo en minúsculas
    WHEN: Se construye el Value Object
    THEN: Falla aquí y no al escribir en la columna enum de la base de datos

    Sin esta conversión, un 'rfeg' en minúsculas se colaba: no es igual a
    MANUAL, así que pasaba por campo importado y reventaba mucho más tarde.
    """
    with pytest.raises(ValueError):
        CourseProvenance(source=invalid_source, imported_at=IMPORTED_AT)


def test_a_lowercase_manual_source_does_not_bypass_the_manual_rules():
    """
    GIVEN: El origen manual escrito en minúsculas junto a datos de importación
    WHEN: Se construye el Value Object
    THEN: Falla, en vez de colarse como si fuera un origen externo
    """
    with pytest.raises(ValueError):
        CourseProvenance(source="manual", external_id="915", imported_at=IMPORTED_AT)


def test_external_id_longer_than_limit_is_rejected():
    """
    GIVEN: Un identificador externo de más de 100 caracteres
    WHEN: Se construye el Value Object
    THEN: Falla, porque no cabría en la columna
    """
    with pytest.raises(ValueError, match="at most 100 characters"):
        CourseProvenance(
            source=CourseSource.RFEG, external_id="9" * 101, imported_at=IMPORTED_AT
        )
