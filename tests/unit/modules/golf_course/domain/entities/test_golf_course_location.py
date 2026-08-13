"""
Tests de la ubicación dentro del agregado GolfCourse.

Lo que más se protege aquí es que editar un campo sin enviar ubicación no la
borre: el formulario de edición es anterior a esta funcionalidad y no la manda,
así que la omisión tiene que significar "no la toques".
"""

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]

DERIO = CourseLocation(
    latitude=43.29519,
    longitude=-2.87352,
    address="CALLE EREAGA BIDEA S/N, 48160, DERIO, VIZCAYA",
    city="DERIO",
    province="VIZCAYA",
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


def build_course(location: CourseLocation | None = None) -> GolfCourse:
    """Crea un campo con la ubicación dada."""
    return GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=build_tees(),
        holes=build_holes(),
        location=location,
    )


# ============================================================================
# Tests: creación
# ============================================================================


def test_course_created_with_location_keeps_it():
    """
    GIVEN: Un campo creado con ubicación
    WHEN: Se consulta su ubicación
    THEN: Devuelve los mismos datos
    """
    course = build_course(location=DERIO)

    assert course.location == DERIO
    assert course.location.has_coordinates is True


def test_course_created_without_location_has_empty_one():
    """
    GIVEN: Un campo creado sin ubicación
    WHEN: Se consulta su ubicación
    THEN: Devuelve un Value Object vacío, nunca None
    """
    course = build_course()

    assert course.location.is_empty is True


def test_reconstruct_restores_location():
    """
    GIVEN: Un campo reconstruido desde persistencia con ubicación
    WHEN: Se consulta su ubicación
    THEN: La conserva
    """
    original = build_course(location=DERIO)

    restored = GolfCourse.reconstruct(
        id=original.id,
        name=original.name,
        country_code=original.country_code,
        course_type=original.course_type,
        creator_id=original.creator_id,
        tees=build_tees(),
        holes=build_holes(),
        approval_status=original.approval_status,
        rejection_reason=None,
        created_at=original.created_at,
        updated_at=original.updated_at,
        location=DERIO,
    )

    assert restored.location == DERIO


# ============================================================================
# Tests: la edición no borra la ubicación
# ============================================================================


def test_update_without_location_keeps_the_existing_one():
    """
    GIVEN: Un campo con ubicación
    WHEN: Se edita sin enviar ubicación (lo que hace el formulario actual)
    THEN: La ubicación se conserva
    """
    course = build_course(location=DERIO)

    course.update(
        name="Nombre nuevo",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
    )

    assert course.location == DERIO
    assert course.name == "Nombre nuevo"


def test_update_with_empty_location_clears_it():
    """
    GIVEN: Un campo con ubicación
    WHEN: Se edita enviando una ubicación explícitamente vacía
    THEN: La ubicación se borra
    """
    course = build_course(location=DERIO)

    course.update(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        location=CourseLocation(),
    )

    assert course.location.is_empty is True


def test_update_with_a_partial_location_replaces_the_whole_object():
    """
    GIVEN: Un campo con coordenadas, dirección, localidad y provincia
    WHEN: Se edita enviando una ubicación con solo la localidad
    THEN: La ubicación se reemplaza entera y el resto queda vacío

    La ubicación no se parchea campo a campo: se comporta igual que `tees` y
    `holes` en la misma petición, que también se reemplazan enteros.
    """
    course = build_course(location=DERIO)

    course.update(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        location=CourseLocation(city="MARBELLA"),
    )

    assert course.location.city == "MARBELLA"
    assert course.location.has_coordinates is False
    assert course.location.address is None


def test_update_with_new_location_replaces_it():
    """
    GIVEN: Un campo con ubicación
    WHEN: Se edita con una ubicación distinta
    THEN: Queda la nueva
    """
    course = build_course(location=DERIO)
    marbella = CourseLocation(latitude=36.5, longitude=-4.9, city="MARBELLA")

    course.update(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        location=marbella,
    )

    assert course.location == marbella


# ============================================================================
# Tests: propuestas de cambio (clones)
# ============================================================================


def test_clone_inherits_location_when_the_edit_omits_it():
    """
    GIVEN: Un campo APPROVED con ubicación, editado por su creator
    WHEN: Se genera el clone de propuesta sin enviar ubicación
    THEN: El clone hereda la ubicación, para que aprobarlo no la borre
    """
    course = build_course(location=DERIO)
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
    assert clone.location == DERIO


def test_approving_a_clone_copies_its_location_to_the_original():
    """
    GIVEN: Un clone con una ubicación nueva
    WHEN: Se aplican sus cambios al campo original
    THEN: El original queda con la ubicación del clone
    """
    course = build_course()
    course.approve()
    marbella = CourseLocation(latitude=36.5, longitude=-4.9, city="MARBELLA")

    clone = course.apply_update(
        name="Nombre nuevo",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        is_admin=False,
        location=marbella,
    )
    assert clone is not None

    course.apply_changes_from_clone(clone)

    assert course.location == marbella


def test_admin_edit_applies_location_in_place():
    """
    GIVEN: Un campo APPROVED editado por un admin
    WHEN: La edición trae ubicación nueva
    THEN: Se aplica directamente, sin crear clone
    """
    course = build_course()
    course.approve()
    marbella = CourseLocation(latitude=36.5, longitude=-4.9, city="MARBELLA")

    clone = course.apply_update(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=build_tees(),
        holes=build_holes(),
        is_admin=True,
        location=marbella,
    )

    assert clone is None
    assert course.location == marbella
