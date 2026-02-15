"""
Integration tests for GolfCourseRepository.

Tests the complete persistence layer: Repository + SQLAlchemy Mapper + PostgreSQL.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = [pytest.mark.integration]


# ============================================================================
# Helper: insert minimal user row for FK constraints
# ============================================================================


async def _insert_test_user(db_session, user_id: UserId) -> None:
    """Insert a minimal user row so golf_courses.creator_id FK is satisfied."""
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, password, "
            "created_at, updated_at, email_verified, failed_login_attempts, is_admin) "
            "VALUES (:id, :fn, :ln, :email, :pw, :ca, :ua, :ev, :fla, :ia)"
        ),
        {
            "id": str(user_id.value),
            "fn": "Test",
            "ln": "User",
            "email": f"test-{user_id.value}@example.com",
            "pw": "$2b$04$placeholder",
            "ca": now,
            "ua": now,
            "ev": False,
            "fla": 0,
            "ia": False,
        },
    )


@pytest_asyncio.fixture
async def creator_id(db_session) -> UserId:
    """Provide a UserId backed by an actual user row in the test DB."""
    uid = UserId.generate()
    await _insert_test_user(db_session, uid)
    return uid


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def valid_tees():
    """Crea 3 tees válidos para tests de integración."""
    return [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            identifier="Blanco",
            course_rating=73.5,
            slope_rating=135,
        ),
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            identifier="Amarillo",
            course_rating=71.2,
            slope_rating=128,
        ),
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.FEMALE,
            identifier="Rojo",
            course_rating=75.0,
            slope_rating=140,
        ),
    ]


@pytest.fixture
def valid_holes():
    """Crea 18 hoyos válidos para tests de integración."""
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
# Tests: save() + find_by_id()
# ============================================================================


async def test_save_and_find_by_id(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo de golf nuevo
    WHEN: Se persiste y se busca por ID
    THEN: Se recupera correctamente con todas sus propiedades
    """
    # Arrange
    golf_course = GolfCourse.create(
        name="Real Club de Golf El Prat",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    repository = GolfCourseRepository(db_session)

    # Act
    await repository.save(golf_course)
    await db_session.commit()

    # Assert
    retrieved = await repository.find_by_id(golf_course.id)
    assert retrieved is not None
    assert retrieved.id == golf_course.id
    assert retrieved.name == "Real Club de Golf El Prat"
    assert retrieved.country_code == CountryCode("ES")
    assert retrieved.course_type == CourseType.STANDARD_18
    assert retrieved.creator_id == creator_id
    assert retrieved.approval_status == ApprovalStatus.PENDING_APPROVAL
    assert retrieved.rejection_reason is None
    assert len(retrieved.tees) == 3
    assert len(retrieved.holes) == 18
    assert retrieved.total_par == 72


async def test_find_by_id_non_existent(db_session):
    """
    GIVEN: Un ID que no existe en BD
    WHEN: Se busca por ID
    THEN: Se retorna None
    """
    # Arrange
    repository = GolfCourseRepository(db_session)
    fake_id = GolfCourseId.generate()

    # Act
    result = await repository.find_by_id(fake_id)

    # Assert
    assert result is None


async def test_save_updates_existing_golf_course(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo ya persistido
    WHEN: Se modifica (approve) y se guarda
    THEN: Los cambios se persisten correctamente
    """
    # Arrange
    golf_course = GolfCourse.create(
        name="Campo Test",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    repository = GolfCourseRepository(db_session)
    await repository.save(golf_course)
    await db_session.commit()

    # Act - Aprobar el campo
    golf_course.approve()
    await repository.save(golf_course)
    await db_session.commit()

    # Assert
    retrieved = await repository.find_by_id(golf_course.id)
    assert retrieved is not None
    assert retrieved.approval_status == ApprovalStatus.APPROVED
    assert retrieved.rejection_reason is None


# ============================================================================
# Tests: find_by_approval_status()
# ============================================================================


async def test_find_by_approval_status_pending(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: 3 campos (2 PENDING, 1 APPROVED)
    WHEN: Se busca por status PENDING_APPROVAL
    THEN: Se retornan solo los 2 campos pendientes
    """
    # Arrange
    repository = GolfCourseRepository(db_session)

    # Crear 2 campos pendientes
    golf_course1 = GolfCourse.create(
        name="Campo Pendiente 1",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course2 = GolfCourse.create(
        name="Campo Pendiente 2",
        country_code=CountryCode("FR"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    await repository.save(golf_course1)
    await repository.save(golf_course2)

    # Crear 1 campo aprobado
    golf_course3 = GolfCourse.create(
        name="Campo Aprobado",
        country_code=CountryCode("US"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course3.approve()
    await repository.save(golf_course3)
    await db_session.commit()

    # Act
    pending_courses = await repository.find_by_approval_status(ApprovalStatus.PENDING_APPROVAL)

    # Assert
    assert len(pending_courses) == 2
    names = {course.name for course in pending_courses}
    assert "Campo Pendiente 1" in names
    assert "Campo Pendiente 2" in names
    assert all(
        course.approval_status == ApprovalStatus.PENDING_APPROVAL for course in pending_courses
    )


async def test_find_by_approval_status_approved(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: 3 campos (1 PENDING, 2 APPROVED)
    WHEN: Se busca por status APPROVED
    THEN: Se retornan solo los 2 campos aprobados
    """
    # Arrange
    repository = GolfCourseRepository(db_session)

    # Crear 1 campo pendiente
    golf_course1 = GolfCourse.create(
        name="Campo Pendiente",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    await repository.save(golf_course1)

    # Crear 2 campos aprobados
    golf_course2 = GolfCourse.create(
        name="Campo Aprobado 1",
        country_code=CountryCode("FR"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course2.approve()
    await repository.save(golf_course2)

    golf_course3 = GolfCourse.create(
        name="Campo Aprobado 2",
        country_code=CountryCode("US"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course3.approve()
    await repository.save(golf_course3)
    await db_session.commit()

    # Act
    approved_courses = await repository.find_by_approval_status(ApprovalStatus.APPROVED)

    # Assert
    assert len(approved_courses) == 2
    names = {course.name for course in approved_courses}
    assert "Campo Aprobado 1" in names
    assert "Campo Aprobado 2" in names
    assert all(course.approval_status == ApprovalStatus.APPROVED for course in approved_courses)


async def test_find_by_approval_status_rejected(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: 3 campos (1 PENDING, 1 APPROVED, 1 REJECTED)
    WHEN: Se busca por status REJECTED
    THEN: Se retorna solo el campo rechazado
    """
    # Arrange
    repository = GolfCourseRepository(db_session)

    # Crear campos con diferentes estados
    golf_course1 = GolfCourse.create(
        name="Campo Pendiente",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    await repository.save(golf_course1)

    golf_course2 = GolfCourse.create(
        name="Campo Aprobado",
        country_code=CountryCode("FR"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course2.approve()
    await repository.save(golf_course2)

    golf_course3 = GolfCourse.create(
        name="Campo Rechazado",
        country_code=CountryCode("US"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    golf_course3.reject(reason="Ratings WHS incorrectos")
    await repository.save(golf_course3)
    await db_session.commit()

    # Act
    rejected_courses = await repository.find_by_approval_status(ApprovalStatus.REJECTED)

    # Assert
    assert len(rejected_courses) == 1
    assert rejected_courses[0].name == "Campo Rechazado"
    assert rejected_courses[0].approval_status == ApprovalStatus.REJECTED
    assert rejected_courses[0].rejection_reason == "Ratings WHS incorrectos"


# ============================================================================
# Tests: find_approved() + find_pending_approval()
# ============================================================================


async def test_find_approved(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Varios campos con diferentes estados
    WHEN: Se llama a find_approved()
    THEN: Se retornan solo los aprobados
    """
    # Arrange
    repository = GolfCourseRepository(db_session)

    # Crear 2 aprobados
    for i in range(1, 3):
        golf_course = GolfCourse.create(
            name=f"Campo Aprobado {i}",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=valid_tees,
            holes=valid_holes,
        )
        golf_course.approve()
        await repository.save(golf_course)

    # Crear 1 pendiente
    pending_course = GolfCourse.create(
        name="Campo Pendiente",
        country_code=CountryCode("FR"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    await repository.save(pending_course)
    await db_session.commit()

    # Act
    approved = await repository.find_approved()

    # Assert
    assert len(approved) == 2
    assert all(course.approval_status == ApprovalStatus.APPROVED for course in approved)


async def test_find_pending_approval(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Varios campos con diferentes estados
    WHEN: Se llama a find_pending_approval()
    THEN: Se retornan solo los pendientes
    """
    # Arrange
    repository = GolfCourseRepository(db_session)

    # Crear 3 pendientes
    for i in range(1, 4):
        golf_course = GolfCourse.create(
            name=f"Campo Pendiente {i}",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=valid_tees,
            holes=valid_holes,
        )
        await repository.save(golf_course)

    # Crear 1 aprobado
    approved_course = GolfCourse.create(
        name="Campo Aprobado",
        country_code=CountryCode("FR"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    approved_course.approve()
    await repository.save(approved_course)
    await db_session.commit()

    # Act
    pending = await repository.find_pending_approval()

    # Assert
    assert len(pending) == 3
    assert all(course.approval_status == ApprovalStatus.PENDING_APPROVAL for course in pending)


# ============================================================================
# Tests: find_by_creator()
# ============================================================================


async def test_find_by_creator(db_session, valid_tees, valid_holes):
    """
    GIVEN: 5 campos creados por 2 usuarios diferentes
    WHEN: Se busca por creator_id
    THEN: Se retornan solo los campos de ese creator
    """
    # Arrange
    repository = GolfCourseRepository(db_session)
    creator1 = UserId.generate()
    creator2 = UserId.generate()
    await _insert_test_user(db_session, creator1)
    await _insert_test_user(db_session, creator2)

    # Creator1 crea 3 campos
    for i in range(1, 4):
        golf_course = GolfCourse.create(
            name=f"Campo Creator1-{i}",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator1,
            tees=valid_tees,
            holes=valid_holes,
        )
        await repository.save(golf_course)

    # Creator2 crea 2 campos
    for i in range(1, 3):
        golf_course = GolfCourse.create(
            name=f"Campo Creator2-{i}",
            country_code=CountryCode("FR"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator2,
            tees=valid_tees,
            holes=valid_holes,
        )
        await repository.save(golf_course)
    await db_session.commit()

    # Act
    creator1_courses = await repository.find_by_creator(creator1)
    creator2_courses = await repository.find_by_creator(creator2)

    # Assert
    assert len(creator1_courses) == 3
    assert len(creator2_courses) == 2
    assert all(course.creator_id == creator1 for course in creator1_courses)
    assert all(course.creator_id == creator2 for course in creator2_courses)


async def test_find_by_creator_no_results(db_session):
    """
    GIVEN: Un creator_id sin campos asociados
    WHEN: Se busca por ese creator_id
    THEN: Se retorna lista vacía
    """
    # Arrange
    repository = GolfCourseRepository(db_session)
    fake_creator = UserId.generate()

    # Act
    result = await repository.find_by_creator(fake_creator)

    # Assert
    assert result == []


# ============================================================================
# Tests: delete()
# ============================================================================


async def test_delete_golf_course(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo persistido con tees y holes
    WHEN: Se elimina el campo
    THEN: El campo y sus tees/holes se eliminan (cascade delete)
    """
    # Arrange
    golf_course = GolfCourse.create(
        name="Campo a Eliminar",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=valid_holes,
    )
    repository = GolfCourseRepository(db_session)
    await repository.save(golf_course)
    await db_session.commit()

    # Verificar que existe
    assert await repository.find_by_id(golf_course.id) is not None

    # Act
    await repository.delete(golf_course.id)
    await db_session.commit()

    # Assert - GolfCourse eliminado
    assert await repository.find_by_id(golf_course.id) is None

    # Assert - Cascade delete: Tees eliminados (raw SQL to avoid TypeDecorator issues)
    result_tees = await db_session.execute(
        text("SELECT count(*) FROM golf_course_tees WHERE golf_course_id = :gc_id"),
        {"gc_id": str(golf_course.id.value)},
    )
    assert result_tees.scalar() == 0, "Tees should be cascade deleted"

    # Assert - Cascade delete: Holes eliminados
    result_holes = await db_session.execute(
        text("SELECT count(*) FROM golf_course_holes WHERE golf_course_id = :gc_id"),
        {"gc_id": str(golf_course.id.value)},
    )
    assert result_holes.scalar() == 0, "Holes should be cascade deleted"


async def test_delete_non_existent_golf_course(db_session):
    """
    GIVEN: Un ID que no existe
    WHEN: Se intenta eliminar
    THEN: No se lanza error (operación idempotente)
    """
    # Arrange
    repository = GolfCourseRepository(db_session)
    fake_id = GolfCourseId.generate()

    # Act & Assert - No debe lanzar excepción
    await repository.delete(fake_id)
    await db_session.commit()


# ============================================================================
# Tests: Complex scenarios
# ============================================================================


async def test_repository_handles_multiple_tees(db_session, creator_id, valid_holes):
    """
    GIVEN: Un campo con 6 tees (máximo permitido)
    WHEN: Se persiste y recupera
    THEN: Todos los tees se persisten correctamente
    """
    # Arrange
    all_tees = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            identifier="Negro",
            course_rating=75.0,
            slope_rating=145,
        ),
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            identifier="Blanco",
            course_rating=73.0,
            slope_rating=135,
        ),
        Tee(
            category=TeeCategory.SENIOR,
            gender=Gender.MALE,
            identifier="Amarillo",
            course_rating=71.0,
            slope_rating=128,
        ),
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.FEMALE,
            identifier="Azul",
            course_rating=76.0,
            slope_rating=142,
        ),
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.FEMALE,
            identifier="Rojo",
            course_rating=73.5,
            slope_rating=136,
        ),
        Tee(
            category=TeeCategory.SENIOR,
            gender=Gender.FEMALE,
            identifier="Verde",
            course_rating=71.5,
            slope_rating=130,
        ),
    ]
    golf_course = GolfCourse.create(
        name="Campo con 6 Tees",
        country_code=CountryCode("US"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=all_tees,
        holes=valid_holes,
    )
    repository = GolfCourseRepository(db_session)

    # Act
    await repository.save(golf_course)
    await db_session.commit()

    # Assert
    retrieved = await repository.find_by_id(golf_course.id)
    assert retrieved is not None
    assert len(retrieved.tees) == 6
    # Verificar que las combinaciones (categoría, gender) son únicas
    combos = {(tee.category, tee.gender) for tee in retrieved.tees}
    assert len(combos) == 6


async def test_repository_preserves_hole_order(db_session, creator_id, valid_tees):
    """
    GIVEN: 18 hoyos en orden específico
    WHEN: Se persisten y recuperan
    THEN: El orden se preserva correctamente (1-18)
    """
    # Arrange
    holes_unordered = [
        Hole(number=i, par=4, stroke_index=i) for i in range(18, 0, -1)
    ]  # Orden inverso
    golf_course = GolfCourse.create(
        name="Campo Test Orden",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=valid_tees,
        holes=holes_unordered,
    )
    repository = GolfCourseRepository(db_session)

    # Act
    await repository.save(golf_course)
    await db_session.commit()

    # Assert
    retrieved = await repository.find_by_id(golf_course.id)
    assert retrieved is not None
    assert len(retrieved.holes) == 18
    hole_numbers = [hole.number for hole in retrieved.holes]
    assert hole_numbers == list(range(1, 19))  # Orden preservado 1-18
