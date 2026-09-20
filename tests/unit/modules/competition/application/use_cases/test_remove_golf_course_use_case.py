"""
Tests unitarios para RemoveGolfCourseFromCompetitionUseCase.

Verifica que:
- Se puede eliminar un campo de golf de una competición DRAFT
- Solo el creador puede eliminar campos
- Solo funciona en estado DRAFT
- El campo debe estar previamente asociado
- Se recalcula display_order tras la eliminación
"""

from datetime import date, datetime
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    RemoveGolfCourseRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    GolfCourseHasRoundsError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    CompetitionNotDraftError,
    GolfCourseNotAssignedError,
    RemoveGolfCourseFromCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


@pytest.mark.asyncio
class TestRemoveGolfCourseFromCompetitionUseCase:
    """Tests para RemoveGolfCourseFromCompetitionUseCase."""

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
    async def golf_course(
        self, golf_course_uow: InMemoryGolfCourseUnitOfWork, creator_id: UserId
    ) -> GolfCourse:
        """Fixture que crea un campo de golf APPROVED en España."""
        tees = [
            Tee(
                color=TeeColor.WHITE,
                gender=Gender.MALE,
                identifier="Amarillo",
                course_rating=72.5,
                slope_rating=130,
            ),
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Blanco",
                course_rating=70.0,
                slope_rating=120,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        golf_course = GolfCourse.create(
            name="Real Club Valderrama",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        golf_course._approval_status = ApprovalStatus.APPROVED  # Force approval

        async with golf_course_uow:
            await golf_course_uow.golf_courses.add(golf_course)

        return golf_course

    async def test_should_remove_golf_course_successfully(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que se puede eliminar un campo de golf de una competición.

        Given: Una competición DRAFT con un campo asociado
        When: El creador elimina el campo
        Then: El campo se elimina correctamente
        """
        # Arrange: Añadir el campo primero
        competition.add_golf_course(golf_course.id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        assert response.competition_id == competition.id.value
        assert response.golf_course_id == golf_course.id.value
        assert response.removed_at is not None

        # Verificar que el campo ya no está en la competición
        updated_competition = await competition_uow.competitions.find_by_id(competition.id)
        assert len(updated_competition.golf_courses) == 0

    async def test_should_fail_when_competition_not_found(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta eliminar un campo
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(uuid4()),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_user_not_creator(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        other_user_id: UserId,
    ):
        """
        Verifica que falla cuando el usuario no es el creador.

        Given: Una competición DRAFT con un campo asociado
        When: Un usuario diferente al creador intenta eliminar el campo
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Añadir el campo primero
        competition.add_golf_course(golf_course.id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request_dto, other_user_id)

    async def test_should_fail_when_the_course_already_has_rounds(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que no se quita un campo que ya tiene rondas programadas.

        Given: Una competicion con las inscripciones abiertas y una ronda en ese campo
        When: Se intenta quitar el campo
        Then: Se rechaza — la ronda se quedaria sin donde jugarse

        Antes no hacia falta comprobarlo: no se podian crear rondas hasta
        cerrar inscripciones, y para entonces ya no se tocaban los campos. Al
        abrir la edicion mientras hay inscripciones (BE #323) las dos cosas
        pueden convivir.
        """
        competition.add_golf_course(golf_course.id, CountryCode("ES"))
        competition.activate()
        await competition_uow.competitions.update(competition)
        async with competition_uow:
            await competition_uow.rounds.add(
                Round(
                    id=RoundId.generate(),
                    competition_id=competition.id,
                    golf_course_id=golf_course.id,
                    round_date=date(2026, 6, 1),
                    session_type=SessionType.MORNING,
                    match_format=MatchFormat.FOURBALL,
                    status=RoundStatus.SCHEDULED,
                    handicap_mode=None,
                    allowance_percentage=None,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            await competition_uow.commit()

        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        with pytest.raises(GolfCourseHasRoundsError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_once_enrollment_is_closed(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando las inscripciones ya se han cerrado.

        Given: Una competición CLOSED con un campo asociado
        When: Se intenta eliminar el campo
        Then: Se lanza CompetitionNotDraftError
        """
        # Arrange: añadir el campo y cerrar las inscripciones (BE #323: con
        # ellas abiertas todavía se puede tocar)
        competition.add_golf_course(golf_course.id, CountryCode("ES"))
        competition.activate()
        competition.close_enrollments()
        await competition_uow.competitions.update(competition)

        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(CompetitionNotDraftError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_fail_when_golf_course_not_assigned(
        self,
        competition_uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course: GolfCourse,
        creator_id: UserId,
    ):
        """
        Verifica que falla cuando el campo no está asociado a la competición.

        Given: Una competición DRAFT sin el campo asociado
        When: Se intenta eliminar el campo
        Then: Se lanza GolfCourseNotAssignedError
        """
        # Arrange: No añadir el campo a la competición
        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(golf_course.id.value),
        )

        # Act & Assert
        with pytest.raises(GolfCourseNotAssignedError):
            await use_case.execute(request_dto, creator_id)

    async def test_should_recalculate_display_order_after_removal(
        self,
        competition_uow: InMemoryUnitOfWork,
        golf_course_uow: InMemoryGolfCourseUnitOfWork,
        competition: Competition,
        creator_id: UserId,
    ):
        """
        Verifica que display_order se recalcula tras eliminar un campo del medio.

        Given: Una competición con 3 campos (order 1, 2, 3)
        When: Se elimina el campo del medio (order 2)
        Then: El campo 3 pasa a tener order 2
        """
        # Arrange: Crear 3 campos
        tees = [
            Tee(
                color=TeeColor.WHITE,
                gender=Gender.MALE,
                identifier="Amarillo",
                course_rating=72.0,
                slope_rating=130,
            ),
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Blanco",
                course_rating=70.0,
                slope_rating=120,
            ),
        ]
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

        gc1 = GolfCourse.create(
            name="Campo 1",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        gc1._approval_status = ApprovalStatus.APPROVED

        gc2 = GolfCourse.create(
            name="Campo 2",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        gc2._approval_status = ApprovalStatus.APPROVED

        gc3 = GolfCourse.create(
            name="Campo 3",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
        )
        gc3._approval_status = ApprovalStatus.APPROVED

        # Añadir los 3 campos
        competition.add_golf_course(gc1.id, CountryCode("ES"))
        competition.add_golf_course(gc2.id, CountryCode("ES"))
        competition.add_golf_course(gc3.id, CountryCode("ES"))
        await competition_uow.competitions.update(competition)

        # Verificar orden inicial
        assert len(competition.golf_courses) == 3
        assert competition.golf_courses[0].display_order == 1
        assert competition.golf_courses[1].display_order == 2
        assert competition.golf_courses[2].display_order == 3

        # Act: Eliminar el campo del medio (gc2)
        use_case = RemoveGolfCourseFromCompetitionUseCase(uow=competition_uow)
        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=str(competition.id.value),
            golf_course_id=str(gc2.id.value),
        )
        await use_case.execute(request_dto, creator_id)

        # Assert: Verificar que quedan 2 campos con orden correcto
        updated_competition = await competition_uow.competitions.find_by_id(competition.id)
        assert len(updated_competition.golf_courses) == 2
        assert updated_competition.golf_courses[0].golf_course_id == gc1.id
        assert updated_competition.golf_courses[0].display_order == 1
        assert updated_competition.golf_courses[1].golf_course_id == gc3.id
        assert updated_competition.golf_courses[1].display_order == 2  # ¡Recalculado!
