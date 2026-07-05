"""Tests para SetCustomHandicapUseCase."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    SetCustomHandicapRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    HandicapEditNotAllowedError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    EnrollmentNotFoundError,
    NotCreatorError,
    SetCustomHandicapUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment, EnrollmentStateError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class TestSetCustomHandicapUseCase:
    """Suite de tests para el caso de uso SetCustomHandicapUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        return UserId(uuid4())

    @pytest.fixture
    def player_id(self) -> UserId:
        return UserId(uuid4())

    @pytest.fixture
    def admin_user_id(self) -> UserId:
        return UserId(uuid4())

    async def _create_competition(self, uow: InMemoryUnitOfWork, creator_id: UserId):
        """Helper: crea una competición en DRAFT."""
        create_uc = CreateCompetitionUseCase(uow)
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=24,
        )
        return await create_uc.execute(request, creator_id)

    async def _set_competition_status(
        self, uow: InMemoryUnitOfWork, competition_id, status: str
    ):
        """Helper: mueve una competición a través de sus transiciones hasta `status`."""
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(competition_id))
            if status in ("ACTIVE", "CLOSED", "IN_PROGRESS", "COMPLETED", "CANCELLED"):
                competition.activate()
            if status in ("CLOSED", "IN_PROGRESS", "COMPLETED"):
                competition.close_enrollments()
            if status in ("IN_PROGRESS", "COMPLETED"):
                competition.start()
            if status == "COMPLETED":
                competition.complete()
            if status == "CANCELLED":
                competition.cancel()
            await uow.competitions.update(competition)
            await uow.commit()

    async def _create_approved_enrollment(
        self, uow: InMemoryUnitOfWork, competition_id, user_id: UserId
    ) -> Enrollment:
        """Helper: crea un enrollment ya aprobado."""
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(competition_id),
            user_id=user_id,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()
        return enrollment

    async def test_should_set_custom_handicap_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment aprobado en una competición ACTIVE
        When: El creador establece un hándicap personalizado
        Then: El enrollment refleja el nuevo hándicap
        """
        created = await self._create_competition(uow, creator_id)
        await self._set_competition_status(uow, created.id, "ACTIVE")
        enrollment = await self._create_approved_enrollment(uow, created.id, player_id)

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("15.5")
        )
        response = await use_case.execute(request, creator_id)

        assert response.custom_handicap == Decimal("15.5")

    async def test_should_allow_admin_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        player_id: UserId,
        admin_user_id: UserId,
    ):
        """
        Given: Un enrollment aprobado en una competición ajena
        When: Un admin (no creador) establece el hándicap con is_admin=True
        Then: Se aplica sin lanzar NotCreatorError
        """
        created = await self._create_competition(uow, creator_id)
        await self._set_competition_status(uow, created.id, "ACTIVE")
        enrollment = await self._create_approved_enrollment(uow, created.id, player_id)

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("10.0")
        )
        response = await use_case.execute(request, admin_user_id, is_admin=True)

        assert response.custom_handicap == Decimal("10.0")

    async def test_should_raise_not_creator_error(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment aprobado
        When: Un usuario que no es el creador ni admin intenta establecer el hándicap
        Then: Se lanza NotCreatorError
        """
        created = await self._create_competition(uow, creator_id)
        await self._set_competition_status(uow, created.id, "ACTIVE")
        enrollment = await self._create_approved_enrollment(uow, created.id, player_id)

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("10.0")
        )

        with pytest.raises(NotCreatorError):
            await use_case.execute(request, player_id)

    async def test_should_raise_enrollment_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un enrollment_id que no existe
        When: Se intenta establecer el hándicap
        Then: Se lanza EnrollmentNotFoundError
        """
        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=uuid4(), custom_handicap=Decimal("10.0")
        )

        with pytest.raises(EnrollmentNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_competition_not_found(self, uow: InMemoryUnitOfWork, creator_id: UserId):
        """
        Given: Un enrollment cuya competición no existe
        When: Se intenta establecer el hándicap
        Then: Se lanza CompetitionNotFoundError
        """
        fake_comp_id = CompetitionId(uuid4())
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=fake_comp_id,
            user_id=creator_id,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("10.0")
        )

        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_enrollment_state_error_when_not_approved(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment en estado REQUESTED (no aprobado)
        When: El creador intenta establecer el hándicap
        Then: Se lanza EnrollmentStateError
        """
        created = await self._create_competition(uow, creator_id)
        await self._set_competition_status(uow, created.id, "ACTIVE")
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(created.id),
            user_id=player_id,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("10.0")
        )

        with pytest.raises(EnrollmentStateError):
            await use_case.execute(request, creator_id)

    @pytest.mark.parametrize("status", ["IN_PROGRESS", "COMPLETED", "CANCELLED"])
    async def test_should_raise_handicap_edit_not_allowed_once_competition_left_closed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId, status: str
    ):
        """
        Given: Un enrollment aprobado en una competición IN_PROGRESS/COMPLETED/CANCELLED
        When: El creador intenta establecer el hándicap
        Then: Se lanza HandicapEditNotAllowedError
        """
        created = await self._create_competition(uow, creator_id)
        enrollment = await self._create_approved_enrollment(uow, created.id, player_id)
        await self._set_competition_status(uow, created.id, status)

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("10.0")
        )

        with pytest.raises(HandicapEditNotAllowedError):
            await use_case.execute(request, creator_id)

    @pytest.mark.parametrize("status", ["DRAFT", "ACTIVE", "CLOSED"])
    async def test_should_allow_handicap_edit_while_draft_active_or_closed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId, status: str
    ):
        """
        Given: Un enrollment aprobado
        When: La competición está en DRAFT, ACTIVE o CLOSED
        Then: Se puede establecer el hándicap personalizado sin errores
        """
        created = await self._create_competition(uow, creator_id)
        enrollment = await self._create_approved_enrollment(uow, created.id, player_id)
        await self._set_competition_status(uow, created.id, status)

        use_case = SetCustomHandicapUseCase(uow)
        request = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment.id.value, custom_handicap=Decimal("11.0")
        )

        response = await use_case.execute(request, creator_id)
        assert response.custom_handicap == Decimal("11.0")
