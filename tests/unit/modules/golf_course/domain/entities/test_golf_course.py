"""
Tests unitarios para GolfCourse aggregate.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.events.golf_course_approved_event import GolfCourseApprovedEvent
from src.modules.golf_course.domain.events.golf_course_rejected_event import GolfCourseRejectedEvent
from src.modules.golf_course.domain.events.golf_course_requested_event import GolfCourseRequestedEvent
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def valid_tees():
    """Crea 3 tees válidos para tests."""
    return [
        Tee(
            category=TeeCategory.CHAMPIONSHIP_MALE,
            identifier="Blanco",
            course_rating=73.5,
            slope_rating=135,
        ),
        Tee(
            category=TeeCategory.AMATEUR_MALE,
            identifier="Amarillo",
            course_rating=71.2,
            slope_rating=128,
        ),
        Tee(
            category=TeeCategory.CHAMPIONSHIP_FEMALE,
            identifier="Rojo",
            course_rating=75.0,
            slope_rating=140,
        ),
    ]


@pytest.fixture
def valid_holes():
    """Crea 18 hoyos válidos para tests."""
    return [
        Hole(number=i, par=par, stroke_index=si)
        for i, par, si in [
            (1, 4, 5),
            (2, 5, 1),
            (3, 3, 17),
            (4, 4, 9),
            (5, 4, 11),
            (6, 3, 15),
            (7, 5, 3),
            (8, 4, 7),
            (9, 4, 13),
            (10, 4, 6),
            (11, 5, 2),
            (12, 3, 18),
            (13, 4, 10),
            (14, 4, 12),
            (15, 3, 16),
            (16, 5, 4),
            (17, 4, 8),
            (18, 4, 14),
        ]
    ]


# ============================================================================
# Tests: GolfCourse.create()
# ============================================================================


def test_create_golf_course_success(valid_tees, valid_holes):
    """
    GIVEN: Datos válidos para un campo de golf
    WHEN: Se crea un GolfCourse con create()
    THEN: El campo se crea en estado PENDING_APPROVAL con evento registrado
    """
    # Given
    name = "Real Club de Golf El Prat"
    country_code = CountryCode("ES")
    course_type = CourseType.STANDARD_18
    creator_id = UserId.generate()

    # When
    golf_course = GolfCourse.create(
        name=name,
        country_code=country_code,
        course_type=course_type,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )

    # Then
    assert golf_course.id is not None
    assert golf_course.name == name
    assert golf_course.country_code == country_code
    assert golf_course.course_type == course_type
    assert golf_course.creator_id == creator_id
    assert len(golf_course.tees) == 3
    assert len(golf_course.holes) == 18
    assert golf_course.approval_status == ApprovalStatus.PENDING_APPROVAL
    assert golf_course.rejection_reason is None
    assert golf_course.total_par == 72  # sum of pars
    assert isinstance(golf_course.created_at, datetime)
    assert isinstance(golf_course.updated_at, datetime)

    # Event registrado
    events = golf_course.pull_domain_events()
    assert len(events) == 1
    assert isinstance(events[0], GolfCourseRequestedEvent)
    assert events[0].golf_course_id == str(golf_course.id)
    assert events[0].golf_course_name == name
    assert events[0].creator_id == str(creator_id)


def test_create_golf_course_invalid_name_too_short(valid_tees, valid_holes):
    """
    GIVEN: Nombre del campo muy corto (< 3 caracteres)
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    short_name = "RC"  # 2 caracteres

    # When/Then
    with pytest.raises(ValueError, match="Course name must be between 3 and 200 characters"):
        GolfCourse.create(
            name=short_name,
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=valid_holes,
        )


def test_create_golf_course_invalid_name_too_long(valid_tees, valid_holes):
    """
    GIVEN: Nombre del campo muy largo (> 200 caracteres)
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    long_name = "A" * 201  # 201 caracteres

    # When/Then
    with pytest.raises(ValueError, match="Course name must be between 3 and 200 characters"):
        GolfCourse.create(
            name=long_name,
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=valid_holes,
        )


def test_create_golf_course_invalid_holes_count(valid_tees):
    """
    GIVEN: Número incorrecto de hoyos (no 18)
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    invalid_holes = [
        Hole(number=1, par=4, stroke_index=1),
        Hole(number=2, par=5, stroke_index=2),
    ]  # Solo 2 hoyos

    # When/Then
    with pytest.raises(ValueError, match="Golf course must have exactly 18 holes"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=invalid_holes,
        )


def test_create_golf_course_duplicate_stroke_indices(valid_tees):
    """
    GIVEN: Hoyos con stroke indices duplicados
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    holes_with_duplicates = [
        Hole(number=i, par=4, stroke_index=1)  # Todos tienen SI=1 (duplicado)
        for i in range(1, 19)
    ]

    # When/Then
    with pytest.raises(ValueError, match="Stroke indices must be unique"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=holes_with_duplicates,
        )


def test_create_golf_course_invalid_stroke_indices_range(valid_tees):
    """
    GIVEN: Hoyos con stroke indices que no cubren el rango completo 1-18
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given - Usa índices 2-19 (falta el 1, sobra el 19)
    # Pero 19 es inválido, así que mejor usar 1-17 y repetir el 17
    holes_invalid_range = [
        Hole(number=i, par=4, stroke_index=min(i, 17))  # SI 1-17, repite 17 (falta 18)
        for i in range(1, 19)
    ]

    # When/Then - La validación de duplicados ocurre antes que la de rango
    with pytest.raises(ValueError, match="Stroke indices must be unique"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=holes_invalid_range,
        )


def test_create_golf_course_invalid_par_total_too_low(valid_tees):
    """
    GIVEN: Par total < 66
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    holes_par_too_low = [
        Hole(number=i, par=3, stroke_index=i)  # Par total = 54 (demasiado bajo)
        for i in range(1, 19)
    ]

    # When/Then
    with pytest.raises(ValueError, match="Total par must be between 66 and 76"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=holes_par_too_low,
        )


def test_create_golf_course_invalid_par_total_too_high(valid_tees):
    """
    GIVEN: Par total > 76
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    holes_par_too_high = [
        Hole(number=i, par=5, stroke_index=i)  # Par total = 90 (demasiado alto)
        for i in range(1, 19)
    ]

    # When/Then
    with pytest.raises(ValueError, match="Total par must be between 66 and 76"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=valid_tees,
            holes=holes_par_too_high,
        )


def test_create_golf_course_invalid_tees_count_too_few(valid_holes):
    """
    GIVEN: Menos de 2 tees
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given
    only_one_tee = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP_MALE,
            identifier="Blanco",
            course_rating=73.5,
            slope_rating=135,
        )
    ]

    # When/Then
    with pytest.raises(ValueError, match="Golf course must have between 2 and 6 tees"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=only_one_tee,
            holes=valid_holes,
        )


def test_create_golf_course_invalid_tees_count_too_many(valid_holes):
    """
    GIVEN: Más de 6 tees
    WHEN: Se intenta crear un GolfCourse
    THEN: Se lanza ValueError
    """
    # Given - Usar las 6 categorías reales + 1 repetida = 7 tees
    all_categories = [
        TeeCategory.CHAMPIONSHIP_MALE,
        TeeCategory.AMATEUR_MALE,
        TeeCategory.FORWARD_MALE,
        TeeCategory.CHAMPIONSHIP_FEMALE,
        TeeCategory.AMATEUR_FEMALE,
        TeeCategory.FORWARD_FEMALE,
        TeeCategory.CHAMPIONSHIP_MALE,  # Repetida para hacer 7
    ]
    seven_tees = [
        Tee(
            category=cat,
            identifier=f"Tee {i}",
            course_rating=70.0,
            slope_rating=120,
        )
        for i, cat in enumerate(all_categories)
    ]

    # When/Then
    with pytest.raises(ValueError, match="Golf course must have between 2 and 6 tees"):
        GolfCourse.create(
            name="Test Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=seven_tees,
            holes=valid_holes,
        )


# ============================================================================
# Tests: approve()
# ============================================================================


def test_approve_golf_course_success(valid_tees, valid_holes):
    """
    GIVEN: Un campo en estado PENDING_APPROVAL
    WHEN: Se llama a approve()
    THEN: El campo pasa a APPROVED y se registra un evento
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course.clear_domain_events()  # Limpiar evento de creación

    # When
    golf_course.approve()

    # Then
    assert golf_course.approval_status == ApprovalStatus.APPROVED
    assert golf_course.rejection_reason is None

    # Event registrado
    events = golf_course.pull_domain_events()
    assert len(events) == 1
    assert isinstance(events[0], GolfCourseApprovedEvent)
    assert events[0].golf_course_id == str(golf_course.id)
    assert events[0].golf_course_name == golf_course.name
    assert events[0].creator_id == str(golf_course.creator_id)


def test_approve_golf_course_already_approved(valid_tees, valid_holes):
    """
    GIVEN: Un campo ya aprobado
    WHEN: Se intenta aprobar nuevamente
    THEN: Se lanza ValueError
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course.approve()

    # When/Then
    with pytest.raises(ValueError, match="Cannot approve course in status.*Only PENDING_APPROVAL can be approved"):
        golf_course.approve()


def test_approve_golf_course_already_rejected(valid_tees, valid_holes):
    """
    GIVEN: Un campo rechazado
    WHEN: Se intenta aprobar
    THEN: Se lanza ValueError
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course.reject(reason="Datos incorrectos en los ratings")

    # When/Then
    with pytest.raises(ValueError, match="Cannot approve course in status.*Only PENDING_APPROVAL can be approved"):
        golf_course.approve()


# ============================================================================
# Tests: reject()
# ============================================================================


def test_reject_golf_course_success(valid_tees, valid_holes):
    """
    GIVEN: Un campo en estado PENDING_APPROVAL
    WHEN: Se llama a reject() con razón válida
    THEN: El campo pasa a REJECTED y se registra un evento
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course.clear_domain_events()  # Limpiar evento de creación

    reason = "Los ratings WHS no coinciden con los datos oficiales del campo"

    # When
    golf_course.reject(reason=reason)

    # Then
    assert golf_course.approval_status == ApprovalStatus.REJECTED
    assert golf_course.rejection_reason == reason

    # Event registrado
    events = golf_course.pull_domain_events()
    assert len(events) == 1
    assert isinstance(events[0], GolfCourseRejectedEvent)
    assert events[0].golf_course_id == str(golf_course.id)
    assert events[0].golf_course_name == golf_course.name
    assert events[0].creator_id == str(golf_course.creator_id)
    assert events[0].rejection_reason == reason


def test_reject_golf_course_reason_too_short(valid_tees, valid_holes):
    """
    GIVEN: Una razón de rechazo muy corta (< 10 caracteres)
    WHEN: Se intenta rechazar
    THEN: Se lanza ValueError
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )

    # When/Then
    with pytest.raises(ValueError, match="Rejection reason must be between 10 and 500 characters"):
        golf_course.reject(reason="Mal")  # 3 caracteres


def test_reject_golf_course_reason_too_long(valid_tees, valid_holes):
    """
    GIVEN: Una razón de rechazo muy larga (> 500 caracteres)
    WHEN: Se intenta rechazar
    THEN: Se lanza ValueError
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )

    # When/Then
    long_reason = "A" * 501  # 501 caracteres
    with pytest.raises(ValueError, match="Rejection reason must be between 10 and 500 characters"):
        golf_course.reject(reason=long_reason)


def test_reject_golf_course_already_approved(valid_tees, valid_holes):
    """
    GIVEN: Un campo ya aprobado
    WHEN: Se intenta rechazar
    THEN: Se lanza ValueError (estado inmutable)
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course.approve()

    # When/Then
    with pytest.raises(ValueError, match="Cannot reject course in status.*Only PENDING_APPROVAL can be rejected"):
        golf_course.reject(reason="Razón de rechazo válida pero estado no lo permite")


def test_reject_golf_course_already_rejected(valid_tees, valid_holes):
    """
    GIVEN: Un campo ya rechazado
    WHEN: Se intenta rechazar nuevamente
    THEN: Se lanza ValueError (estado inmutable)
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course.reject(reason="Primera razón de rechazo válida")

    # When/Then
    with pytest.raises(ValueError, match="Cannot reject course in status.*Only PENDING_APPROVAL can be rejected"):
        golf_course.reject(reason="Segunda razón de rechazo válida pero estado no lo permite")


# ============================================================================
# Tests: reconstruct()
# ============================================================================


def test_reconstruct_golf_course_success(valid_tees, valid_holes):
    """
    GIVEN: Datos completos de un campo desde persistencia
    WHEN: Se reconstruye con reconstruct()
    THEN: El campo se hidrata correctamente SIN registrar eventos
    """
    # Given
    from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

    golf_course_id = GolfCourseId.generate()
    name = "Reconstructed Course"
    country_code = CountryCode("ES")
    course_type = CourseType.STANDARD_18
    creator_id = UserId.generate()
    approval_status = ApprovalStatus.APPROVED
    created_at = datetime(2025, 1, 1, 12, 0, 0)
    updated_at = datetime(2025, 1, 15, 14, 30, 0)

    # When
    golf_course = GolfCourse.reconstruct(
        id=golf_course_id,
        name=name,
        country_code=country_code,
        course_type=course_type,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
        approval_status=approval_status,
        rejection_reason=None,
        created_at=created_at,
        updated_at=updated_at,
    )

    # Then
    assert golf_course.id == golf_course_id
    assert golf_course.name == name
    assert golf_course.approval_status == approval_status
    assert golf_course.created_at == created_at
    assert golf_course.updated_at == updated_at
    assert len(golf_course.pull_domain_events()) == 0  # Sin eventos en reconstrucción


# ============================================================================
# Tests: Properties
# ============================================================================


def test_golf_course_total_par_calculation(valid_tees, valid_holes):
    """
    GIVEN: Un campo con 18 hoyos
    WHEN: Se accede a la propiedad total_par
    THEN: Retorna la suma correcta de pares
    """
    # Given/When
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )

    # Then
    expected_par = sum(h.par for h in valid_holes)
    assert golf_course.total_par == expected_par
    assert golf_course.total_par == 72  # Par específico de valid_holes fixture


def test_golf_course_tees_property_returns_copy(valid_tees, valid_holes):
    """
    GIVEN: Un campo de golf
    WHEN: Se accede a la propiedad tees
    THEN: Retorna una copia (no la lista interna)
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )

    # When
    tees_copy = golf_course.tees

    # Then
    assert tees_copy is not golf_course._tees  # Es una copia
    assert len(tees_copy) == len(valid_tees)


def test_golf_course_holes_property_returns_copy(valid_tees, valid_holes):
    """
    GIVEN: Un campo de golf
    WHEN: Se accede a la propiedad holes
    THEN: Retorna una copia (no la lista interna)
    """
    # Given
    golf_course = GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=valid_tees,
        holes=valid_holes,
    )

    # When
    holes_copy = golf_course.holes

    # Then
    assert holes_copy is not golf_course._holes  # Es una copia
    assert len(holes_copy) == len(valid_holes)
