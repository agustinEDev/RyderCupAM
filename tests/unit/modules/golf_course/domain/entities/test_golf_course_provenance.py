"""
Tests de la procedencia y los hoyos físicos dentro del agregado GolfCourse.

La regla que más se protege: una edición a mano no puede convertir un campo
federado en otra cosa, ni al revés. La procedencia solo cambia si quien edita
la trae explícitamente, que en la práctica es el importador.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_provenance import CourseProvenance
from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]
IMPORTED_AT = datetime(2026, 8, 12, 10, 0, 0)
RFEG_PROVENANCE = CourseProvenance(
    source=CourseSource.RFEG, external_id="3727", imported_at=IMPORTED_AT
)


def build_holes() -> list[Hole]:
    """Construye una tarjeta de 18 hoyos con índices 1-18."""
    return [Hole(number=i + 1, par=PAR_72[i], stroke_index=i + 1, meters=350) for i in range(18)]


def build_tees() -> list[Tee]:
    """Construye una salida amarilla masculina."""
    return [
        Tee(
            gender=Gender.MALE,
            color=TeeColor.YELLOW,
            identifier=None,
            course_rating=71.2,
            slope_rating=125,
            holes=build_holes(),
        )
    ]


def build_course(
    provenance: CourseProvenance | None = None, physical_holes: int | None = None
) -> GolfCourse:
    """Crea un campo con la procedencia dada."""
    return GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=build_tees(),
        holes=build_holes(),
        provenance=provenance,
        physical_holes=physical_holes,
    )


# ============================================================================
# Tests: creación
# ============================================================================


def test_course_without_provenance_is_manual():
    """
    GIVEN: Un campo creado sin procedencia
    WHEN: Se consulta
    THEN: Consta como dado de alta a mano
    """
    course = build_course()

    assert course.provenance.source is CourseSource.MANUAL
    assert course.provenance.is_imported is False


def test_imported_course_keeps_its_provenance():
    """
    GIVEN: Un campo creado con procedencia de la RFEG
    WHEN: Se consulta
    THEN: Conserva origen, identificador externo y fecha
    """
    course = build_course(provenance=RFEG_PROVENANCE)

    assert course.provenance == RFEG_PROVENANCE


# ============================================================================
# Tests: hoyos físicos
# ============================================================================


@pytest.mark.parametrize("physical_holes", [9, 18])
def test_physical_holes_accepts_nine_and_eighteen(physical_holes):
    """
    GIVEN: Un campo de nueve o de dieciocho hoyos sobre el terreno
    WHEN: Se crea
    THEN: Se guarda el dato
    """
    course = build_course(physical_holes=physical_holes)

    assert course.physical_holes == physical_holes


def test_physical_holes_is_unknown_by_default():
    """
    GIVEN: Un campo creado sin decir cuántos hoyos tiene sobre el terreno
    WHEN: Se consulta
    THEN: Devuelve None, que significa 'no consta'
    """
    course = build_course()

    assert course.physical_holes is None


@pytest.mark.parametrize("invalid", [0, 8, 27, 36])
def test_physical_holes_rejects_other_values(invalid):
    """
    GIVEN: Un número de hoyos físicos que no es 9 ni 18
    WHEN: Se crea el campo
    THEN: Falla: la tarjeta siempre es de 18, así que solo caben esas dos formas
    """
    with pytest.raises(ValueError, match="Physical holes must be 9 or 18"):
        build_course(physical_holes=invalid)


# ============================================================================
# Tests: la edición no altera la procedencia
# ============================================================================


def test_update_without_provenance_keeps_the_existing_one():
    """
    GIVEN: Un campo importado de la RFEG
    WHEN: Se edita sin enviar procedencia
    THEN: Sigue constando como importado de la RFEG
    """
    course = build_course(provenance=RFEG_PROVENANCE, physical_holes=9)

    course.update(
        name="Nombre nuevo",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
    )

    assert course.provenance == RFEG_PROVENANCE
    assert course.physical_holes == 9


def test_reimporting_refreshes_the_import_date():
    """
    GIVEN: Un campo importado
    WHEN: Se vuelve a importar con una fecha posterior
    THEN: La procedencia se actualiza

    Es lo que permite saber cuándo se contrastaron por última vez sus datos con
    la federación.
    """
    course = build_course(provenance=RFEG_PROVENANCE)
    later = CourseProvenance(
        source=CourseSource.RFEG,
        external_id="3727",
        imported_at=datetime(2027, 3, 1, 9, 0, 0),
    )

    course.update(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        provenance=later,
    )

    assert course.provenance.imported_at == datetime(2027, 3, 1, 9, 0, 0)


# ============================================================================
# Tests: propuestas de cambio (clones)
# ============================================================================


def test_clone_inherits_provenance_and_physical_holes():
    """
    GIVEN: Un campo federado APPROVED editado por su creator
    WHEN: Se genera el clone de propuesta
    THEN: El clone hereda procedencia y hoyos físicos

    Sin esto, aprobar un cambio de nombre convertiría un campo federado en uno
    manual y perdería la marca de nueve hoyos.
    """
    course = build_course(provenance=RFEG_PROVENANCE, physical_holes=9)
    course.approve()

    clone = course.apply_update(
        name="Nombre nuevo",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        is_admin=False,
    )

    assert clone is not None
    assert clone.provenance == RFEG_PROVENANCE
    assert clone.physical_holes == 9


def test_approving_a_clone_keeps_the_provenance_on_the_original():
    """
    GIVEN: Un clone de un campo federado
    WHEN: Se aplican sus cambios al original
    THEN: El original sigue constando como federado
    """
    course = build_course(provenance=RFEG_PROVENANCE, physical_holes=9)
    course.approve()
    clone = course.apply_update(
        name="Nombre nuevo",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        is_admin=False,
    )
    assert clone is not None

    course.apply_changes_from_clone(clone)

    assert course.provenance == RFEG_PROVENANCE
    assert course.physical_holes == 9
