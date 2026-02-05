"""Tests para AddGolfCourseToCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    AddGolfCourseRequestDTO,
)
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
    CompetitionNotDraftError,
    CompetitionNotFoundError,
    GolfCourseAlreadyAssignedError,
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
    IncompatibleCountryError,
    NotCompetitionCreatorError,
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

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestAddGolfCourseToCompetitionUseCase:
    """Suite de tests para AddGolfCourseToCompetitionUseCase."""

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
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    @pytest.fixture
    def other_user_id(self) -> UserId:
        """Fixture que proporciona un ID de otro usuario."""
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
    async def golf_course(
        self, golf_course_uow: InMemoryGolfCourseUnitOfWork, creator_id: UserId
    ) -> GolfCourse:
        """Fixture que crea un campo de golf APPROVED en España."""
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="Amarillo",
                course_rating=72.5,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Blanco",
                course_rating=70.0,
                slope_rating=120,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        golf_course = GolfCourse.create(
            name="Real Club de Golf El Prat",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )

        # Aprobar el campo
        golf_course._approval_status = ApprovalStatus.APPROVED

        async with golf_course_uow:
            await golf_course_uow.golf_courses.add(golf_course)

        return golf_course

    async def test_should_add_golf_course_successfully(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que se puede añadir un campo de golf a una competición.

        Given: Una competición DRAFT y un campo APPROVED del mismo país
        When: El creador añade el campo
        Then: El campo se añade correctamente con display_order=1
        """
        # Arrange
        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        assert response.competition_id == competition.id.value
        assert response.golf_course_id == golf_course.id.value
        assert response.display_order == 1
        assert response.added_at is not None

        # Verify in repository
        async with competition_uow:
            stored_competition = await competition_uow.competitions.find_by_id(competition.id)
            assert len(stored_competition._golf_courses) == 1
            assert stored_competition._golf_courses[0].golf_course_id == golf_course.id

    async def test_should_fail_when_competition_not_found(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que falla si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta añadir un campo
        Then: Lanza CompetitionNotFoundError
        """
        # Arrange
        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(uuid4()),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_user_not_creator(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        other_user_id: UserId,
    ):
        """
        Verifica que solo el creador puede añadir campos.

        Given: Una competición creada por otro usuario
        When: Un usuario que no es el creador intenta añadir un campo
        Then: Lanza NotCompetitionCreatorError
        """
        # Arrange
        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request_dto, other_user_id)

    async def test_should_fail_when_competition_not_draft(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que solo se pueden añadir campos en estado DRAFT.

        Given: Una competición en estado ACTIVE
        When: Se intenta añadir un campo
        Then: Lanza CompetitionNotDraftError
        """
        # Arrange
        competition.activate()
        async with competition_uow:
            await competition_uow.competitions.update(competition)

        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(CompetitionNotDraftError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_golf_course_not_found(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        creator_id: UserId,
    ):
        """
        Verifica que falla si el campo de golf no existe.

        Given: Un ID de campo inexistente
        When: Se intenta añadir el campo
        Then: Lanza GolfCourseNotFoundError
        """
        # Arrange
        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(uuid4()),
        )

        # Act & Assert
        with pytest.raises(GolfCourseNotFoundError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_golf_course_not_approved(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        creator_id: UserId,
    ):
        """
        Verifica que solo se pueden añadir campos APPROVED.

        Given: Un campo en estado PENDING_APPROVAL
        When: Se intenta añadir el campo
        Then: Lanza GolfCourseNotApprovedError
        """
        # Arrange
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="Amarillo",
                course_rating=72.5,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Blanco",
                course_rating=70.0,
                slope_rating=120,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        pending_course = GolfCourse.create(
            name="Pending Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        # Status is PENDING_APPROVAL by default

        async with golf_course_uow:
            await golf_course_uow.golf_courses.add(pending_course)

        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(pending_course.id.value),
        )

        # Act & Assert
        with pytest.raises(GolfCourseNotApprovedError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_country_mismatch(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        creator_id: UserId,
    ):
        """
        Verifica que el campo debe ser del país de la competición o adyacente.

        Given: Un campo de golf de Francia (no adyacente a España)
        When: Se intenta añadir a competición española
        Then: Lanza IncompatibleCountryError
        """
        # Arrange
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP_MALE,
                identifier="Jaune",
                course_rating=72.0,
                slope_rating=128,
            ),
            Tee(
                category=TeeCategory.AMATEUR_MALE,
                identifier="Blanc",
                course_rating=70.0,
                slope_rating=120,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        french_course = GolfCourse.create(
            name="Golf National",
            country_code=CountryCode("FR"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        french_course._approval_status = ApprovalStatus.APPROVED

        async with golf_course_uow:
            await golf_course_uow.golf_courses.add(french_course)

        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(french_course.id.value),
        )

        # Act & Assert
        with pytest.raises(IncompatibleCountryError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_duplicate_golf_course(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que no se puede añadir el mismo campo dos veces.

        Given: Un campo ya añadido a la competición
        When: Se intenta añadir el mismo campo de nuevo
        Then: Lanza GolfCourseAlreadyAssignedError
        """
        # Arrange - Add course first time
        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )
        request_dto = AddGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        await use_case.execute(request_dto, creator_id)

        # Act & Assert - Try to add again
        with pytest.raises(GolfCourseAlreadyAssignedError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_assign_correct_display_order(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        creator_id: UserId,
    ):
        """
        Verifica que display_order se asigna correctamente (1, 2, 3...).

        Given: Múltiples campos de golf
        When: Se añaden secuencialmente
        Then: display_order se incrementa automáticamente
        """
        # Arrange - Create 3 golf courses
        courses = []
        for i in range(3):
            tees = [
                Tee(
                    category=TeeCategory.CHAMPIONSHIP_MALE,
                    identifier=f"Tee{i}",
                    course_rating=72.0,
                    slope_rating=130,
                ),
                Tee(
                    category=TeeCategory.AMATEUR_MALE,
                    identifier=f"Blanco{i}",
                    course_rating=70.0,
                    slope_rating=120,
                ),
            ]
            holes = [Hole(number=j, par=4, stroke_index=j) for j in range(1, 19)]

            course = GolfCourse.create(
                name=f"Course {i}",
                country_code=CountryCode("ES"),
                course_type=CourseType.STANDARD_18,
                creator_id=creator_id,
                tees=tees,
                holes=holes,
            )
            course._approval_status = ApprovalStatus.APPROVED

            async with golf_course_uow:
                await golf_course_uow.golf_courses.add(course)

            courses.append(course)

        use_case = AddGolfCourseToCompetitionUseCase(
            uow=competition_uow,
            golf_course_repository=golf_course_uow.golf_courses,
        )

        # Act - Add 3 courses
        for idx, course in enumerate(courses):
            request_dto = AddGolfCourseRequestDTO(
                competition_id=str(competition.id.value),
                golf_course_id=str(course.id.value),
            )
            response = await use_case.execute(request_dto, creator_id)

            # Assert - Verify display_order
            assert response.display_order == idx + 1

        # Assert - Verify all stored correctly
        async with competition_uow:
            stored_competition = await competition_uow.competitions.find_by_id(competition.id)
            assert len(stored_competition._golf_courses) == 3
            assert stored_competition._golf_courses[0].display_order == 1
            assert stored_competition._golf_courses[1].display_order == 2
            assert stored_competition._golf_courses[2].display_order == 3
