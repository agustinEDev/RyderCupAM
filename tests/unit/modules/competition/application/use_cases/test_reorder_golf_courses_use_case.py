"""
Tests unitarios para ReorderGolfCoursesUseCase.

Verifica que:
- Se puede reordenar campos de golf de una competición DRAFT
- Solo el creador puede reordenar campos
- Solo funciona en estado DRAFT
- La lista debe incluir TODOS los campos actualmente asociados
- No puede haber duplicados ni IDs faltantes
- Se respeta el orden especificado
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    ReorderGolfCoursesRequestDTO,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    CompetitionNotDraftError,
    CompetitionNotFoundError,
    InvalidReorderError,
    NotCompetitionCreatorError,
    ReorderGolfCoursesUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


@pytest.mark.asyncio
class TestReorderGolfCoursesUseCase:
    """Tests para ReorderGolfCoursesUseCase."""

    @pytest.fixture
    def competition_uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona UoW de Competition en memoria."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def golf_course_uow(self) -> InMemoryGolfCourseUnitOfWork:
        """Fixture que proporciona UoW de GolfCourse en memoria."""
        return InMemoryGolfCourseUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un UserId de creador."""
        return UserId(uuid4())

    @pytest.fixture
    def other_user_id(self) -> UserId:
        """Fixture que proporciona un UserId diferente."""
        return UserId(uuid4())

    @pytest.fixture
    async def competition(
        self, competition_uow: InMemoryUnitOfWork, creator_id: UserId
    ) -> Competition:
        """Fixture que crea una competición en estado DRAFT."""
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Test Competition"),
            dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            max_players=24,
            team_assignment=TeamAssignment.MANUAL,
            team_1_name="Team A",
            team_2_name="Team B",
        )
        async with competition_uow:
            await competition_uow.competitions.add(competition)
        return competition

    @pytest.fixture
    async def three_golf_courses(
        self, golf_course_uow: InMemoryGolfCourseUnitOfWork, creator_id: UserId
    ) -> list[GolfCourse]:
        """Fixture que crea 3 campos de golf APPROVED en España."""
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP,
                gender=Gender.MALE,
                identifier="Amarillo",
                course_rating=72.0,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR,
                gender=Gender.MALE,
                identifier="Blanco",
                course_rating=70.0,
                slope_rating=120,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        courses = []
        async with golf_course_uow:
            for i in range(1, 4):
                gc = GolfCourse.create(
                    name=f"Campo {i}",
                    country_code=CountryCode("ES"),
                    course_type=CourseType.STANDARD_18,
                    creator_id=creator_id,
                    tees=tees,
                    holes=holes,
                )
                gc._approval_status = ApprovalStatus.APPROVED
                await golf_course_uow.golf_courses.add(gc)
                courses.append(gc)
        return courses

    async def test_should_reorder_golf_courses_successfully(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que se puede reordenar campos de golf correctamente.

        Given: Una competición DRAFT con 3 campos (order 1, 2, 3)
        When: El creador reordena a [3, 1, 2]
        Then: Los campos se reordenan correctamente
        """
        # Arrange: Añadir los 3 campos en orden
        for gc in three_golf_courses:
            competition.add_golf_course(gc.id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        # Verificar orden inicial
        assert competition.golf_courses[0].golf_course_id == three_golf_courses[0].id
        assert competition.golf_courses[1].golf_course_id == three_golf_courses[1].id
        assert competition.golf_courses[2].golf_course_id == three_golf_courses[2].id

        # Act: Reordenar a [gc3, gc1, gc2]
        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[2].id.value),  # gc3 → order 1
                str(three_golf_courses[0].id.value),  # gc1 → order 2
                str(three_golf_courses[1].id.value),  # gc2 → order 3
            ],
        )
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        assert response.competition_id == competition.id.value
        assert response.golf_course_count == 3
        assert response.reordered_at is not None

        # Verificar orden actualizado en BD
        updated_competition = await competition_uow.competitions.find_by_id(competition.id)
        assert updated_competition.golf_courses[0].golf_course_id == three_golf_courses[2].id
        assert updated_competition.golf_courses[0].display_order == 1
        assert updated_competition.golf_courses[1].golf_course_id == three_golf_courses[0].id
        assert updated_competition.golf_courses[1].display_order == 2
        assert updated_competition.golf_courses[2].golf_course_id == three_golf_courses[1].id
        assert updated_competition.golf_courses[2].display_order == 3

    async def test_should_reorder_two_courses_successfully(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que se puede reordenar 2 campos (caso común: swap).

        Given: Una competición DRAFT con 2 campos (order 1, 2)
        When: El creador reordena a [2, 1]
        Then: Los campos se intercambian correctamente
        """
        # Arrange: Añadir solo 2 campos
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        # Act: Swap [gc1, gc2] → [gc2, gc1]
        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[1].id.value),  # gc2 → order 1
                str(three_golf_courses[0].id.value),  # gc1 → order 2
            ],
        )
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        assert response.golf_course_count == 2

        updated_competition = await competition_uow.competitions.find_by_id(competition.id)
        assert updated_competition.golf_courses[0].golf_course_id == three_golf_courses[1].id
        assert updated_competition.golf_courses[1].golf_course_id == three_golf_courses[0].id

    async def test_should_fail_when_competition_not_found(
        self,
        competition_uow: InMemoryUnitOfWork,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta reordenar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(uuid4()),
            golf_course_ids=[str(three_golf_courses[0].id.value)],
        )

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_user_not_creator(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        other_user_id: UserId,
    ):
        """
        Verifica que falla cuando el usuario no es el creador.

        Given: Una competición DRAFT con campos
        When: Un usuario diferente al creador intenta reordenar
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Añadir campos
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[1].id.value),
                str(three_golf_courses[0].id.value),
            ],
        )

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request_dto, other_user_id)

    async def test_should_fail_when_competition_not_draft(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando la competición no está en estado DRAFT.

        Given: Una competición ACTIVE con campos
        When: Se intenta reordenar
        Then: Se lanza CompetitionNotDraftError
        """
        # Arrange: Añadir campos y activar
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        competition.activate()
        await competition_uow.competitions.update(competition)

        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[1].id.value),
                str(three_golf_courses[0].id.value),
            ],
        )

        # Act & Assert
        with pytest.raises(CompetitionNotDraftError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_missing_golf_course_ids(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando la lista no incluye todos los campos.

        Given: Una competición con 3 campos
        When: Se intenta reordenar solo 2 campos
        Then: Se lanza InvalidReorderError
        """
        # Arrange: Añadir 3 campos
        for gc in three_golf_courses:
            competition.add_golf_course(gc.id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[0].id.value),
                str(three_golf_courses[1].id.value),
                # Falta gc3
            ],
        )

        # Act & Assert
        with pytest.raises(InvalidReorderError) as exc_info:
            await use_case.execute(request_dto, creator_id)
        assert "Esperados: 3, Recibidos: 2" in str(exc_info.value)

    async def test_should_fail_when_duplicate_golf_course_ids(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando hay IDs duplicados en la lista.

        Given: Una competición con 2 campos
        When: Se intenta reordenar con un ID duplicado
        Then: Se lanza InvalidReorderError
        """
        # Arrange: Añadir 2 campos
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[0].id.value),
                str(three_golf_courses[0].id.value),  # Duplicado
            ],
        )

        # Act & Assert
        with pytest.raises(InvalidReorderError) as exc_info:
            await use_case.execute(request_dto, creator_id)
        assert "no coincide" in str(exc_info.value)

    async def test_should_fail_when_extra_golf_course_ids(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando hay IDs extra que no pertenecen a la competición.

        Given: Una competición con 2 campos
        When: Se intenta reordenar incluyendo un campo externo
        Then: Se lanza InvalidReorderError
        """
        # Arrange: Añadir solo 2 campos
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[0].id.value),
                str(three_golf_courses[1].id.value),
                str(three_golf_courses[2].id.value),  # Extra (no está en competición)
            ],
        )

        # Act & Assert
        with pytest.raises(InvalidReorderError) as exc_info:
            await use_case.execute(request_dto, creator_id)
        assert "Esperados: 2, Recibidos: 3" in str(exc_info.value)

    async def test_should_fail_when_wrong_golf_course_ids(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando los IDs no coinciden con los de la competición.

        Given: Una competición con gc1 y gc2
        When: Se intenta reordenar con gc1 y gc3 (gc3 no está)
        Then: Se lanza InvalidReorderError
        """
        # Arrange: Añadir gc1 y gc2
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[0].id.value),  # gc1 (OK)
                str(three_golf_courses[2].id.value),  # gc3 (NO está en competición)
            ],
        )

        # Act & Assert
        with pytest.raises(InvalidReorderError) as exc_info:
            await use_case.execute(request_dto, creator_id)
        assert "no coincide" in str(exc_info.value)

    async def test_should_handle_reverse_order(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que se puede invertir completamente el orden.

        Given: Una competición con 3 campos [1, 2, 3]
        When: Se reordena a [3, 2, 1]
        Then: El orden se invierte correctamente
        """
        # Arrange: Añadir en orden
        for gc in three_golf_courses:
            competition.add_golf_course(gc.id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        # Act: Invertir orden
        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[2].id.value),  # gc3 → order 1
                str(three_golf_courses[1].id.value),  # gc2 → order 2
                str(three_golf_courses[0].id.value),  # gc1 → order 3
            ],
        )
        await use_case.execute(request_dto, creator_id)

        # Assert
        updated_competition = await competition_uow.competitions.find_by_id(competition.id)
        assert updated_competition.golf_courses[0].golf_course_id == three_golf_courses[2].id
        assert updated_competition.golf_courses[1].golf_course_id == three_golf_courses[1].id
        assert updated_competition.golf_courses[2].golf_course_id == three_golf_courses[0].id

    async def test_should_handle_no_change_order(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        three_golf_courses: list[GolfCourse],
        creator_id: UserId,
    ):
        """
        Verifica que se acepta reordenar con el mismo orden actual.

        Given: Una competición con 2 campos [1, 2]
        When: Se reordena al mismo orden [1, 2]
        Then: La operación se acepta sin cambios
        """
        # Arrange
        competition.add_golf_course(three_golf_courses[0].id, CountryCode("ES"))
        competition.add_golf_course(three_golf_courses[1].id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        # Act: Mismo orden
        use_case = ReorderGolfCoursesUseCase(uow=competition_uow)
        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_ids=[
                str(three_golf_courses[0].id.value),  # gc1 → order 1 (sin cambio)
                str(three_golf_courses[1].id.value),  # gc2 → order 2 (sin cambio)
            ],
        )
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        assert response.golf_course_count == 2

        updated_competition = await competition_uow.competitions.find_by_id(competition.id)
        assert updated_competition.golf_courses[0].golf_course_id == three_golf_courses[0].id
        assert updated_competition.golf_courses[1].golf_course_id == three_golf_courses[1].id
