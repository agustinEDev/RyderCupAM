"""Tests para RemoveCustomHandicapUseCase."""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    HandicapEditNotAllowedError,
)
from src.modules.competition.application.use_cases.remove_custom_handicap_use_case import (
    EnrollmentNotFoundError,
    NotCreatorError,
    RemoveCustomHandicapUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment, EnrollmentStateError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


class TestRemoveCustomHandicapUseCase:
    """Suite de tests para el caso de uso RemoveCustomHandicapUseCase."""

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

    async def test_should_remove_custom_handicap_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment aprobado con hándicap personalizado
        When: El creador lo elimina
        Then: El enrollment vuelve a tener custom_handicap=None
        """
        created = await create_competition(uow, creator_id)
        enrollment = await create_approved_enrollment(
            uow, created.id, player_id, custom_handicap=Decimal("20.0")
        )
        await set_competition_status(uow, created.id, "ACTIVE")

        use_case = RemoveCustomHandicapUseCase(uow)
        response = await use_case.execute(str(enrollment.id.value), creator_id)

        assert response.custom_handicap is None

    async def test_should_allow_admin_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        player_id: UserId,
        admin_user_id: UserId,
    ):
        """
        Given: Un enrollment con hándicap personalizado en una competición ajena
        When: Un admin (no creador) lo elimina con is_admin=True
        Then: Se aplica sin lanzar NotCreatorError
        """
        created = await create_competition(uow, creator_id)
        enrollment = await create_approved_enrollment(
            uow, created.id, player_id, custom_handicap=Decimal("20.0")
        )
        await set_competition_status(uow, created.id, "ACTIVE")

        use_case = RemoveCustomHandicapUseCase(uow)
        response = await use_case.execute(
            str(enrollment.id.value), admin_user_id, is_admin=True
        )

        assert response.custom_handicap is None

    async def test_should_raise_not_creator_error(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment con hándicap personalizado
        When: Un usuario que no es el creador ni admin intenta eliminarlo
        Then: Se lanza NotCreatorError
        """
        created = await create_competition(uow, creator_id)
        enrollment = await create_approved_enrollment(
            uow, created.id, player_id, custom_handicap=Decimal("20.0")
        )
        await set_competition_status(uow, created.id, "ACTIVE")

        use_case = RemoveCustomHandicapUseCase(uow)

        with pytest.raises(NotCreatorError):
            await use_case.execute(str(enrollment.id.value), player_id)

    async def test_should_raise_enrollment_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un enrollment_id que no existe
        When: Se intenta eliminar el hándicap
        Then: Se lanza EnrollmentNotFoundError
        """
        use_case = RemoveCustomHandicapUseCase(uow)

        with pytest.raises(EnrollmentNotFoundError):
            await use_case.execute(str(uuid4()), creator_id)

    async def test_should_raise_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un enrollment cuya competición no existe
        When: Se intenta eliminar el hándicap
        Then: Se lanza CompetitionNotFoundError
        """
        fake_comp_id = CompetitionId(uuid4())
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=fake_comp_id,
            user_id=creator_id,
            custom_handicap=Decimal("20.0"),
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()

        use_case = RemoveCustomHandicapUseCase(uow)

        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(str(enrollment.id.value), creator_id)

    async def test_should_raise_enrollment_state_error_when_not_approved(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment en estado REQUESTED (no aprobado)
        When: El creador intenta eliminar el hándicap
        Then: Se lanza EnrollmentStateError
        """
        created = await create_competition(uow, creator_id)
        await set_competition_status(uow, created.id, "ACTIVE")
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(created.id),
            user_id=player_id,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()

        use_case = RemoveCustomHandicapUseCase(uow)

        with pytest.raises(EnrollmentStateError):
            await use_case.execute(str(enrollment.id.value), creator_id)

    @pytest.mark.parametrize("status", ["IN_PROGRESS", "COMPLETED", "CANCELLED"])
    async def test_should_raise_handicap_edit_not_allowed_once_competition_left_closed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId, status: str
    ):
        """
        Given: Un enrollment con hándicap personalizado en una competición
               IN_PROGRESS/COMPLETED/CANCELLED
        When: El creador intenta eliminar el hándicap
        Then: Se lanza HandicapEditNotAllowedError
        """
        created = await create_competition(uow, creator_id)
        enrollment = await create_approved_enrollment(
            uow, created.id, player_id, custom_handicap=Decimal("20.0")
        )
        await set_competition_status(uow, created.id, status)

        use_case = RemoveCustomHandicapUseCase(uow)

        with pytest.raises(HandicapEditNotAllowedError):
            await use_case.execute(str(enrollment.id.value), creator_id)

    @pytest.mark.parametrize("status", ["DRAFT", "ACTIVE", "CLOSED"])
    async def test_should_allow_handicap_removal_while_draft_active_or_closed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId, status: str
    ):
        """
        Given: Un enrollment con hándicap personalizado
        When: La competición está en DRAFT, ACTIVE o CLOSED
        Then: Se puede eliminar el hándicap personalizado sin errores
        """
        created = await create_competition(uow, creator_id)
        enrollment = await create_approved_enrollment(
            uow, created.id, player_id, custom_handicap=Decimal("20.0")
        )
        await set_competition_status(uow, created.id, status)

        use_case = RemoveCustomHandicapUseCase(uow)
        response = await use_case.execute(str(enrollment.id.value), creator_id)

        assert response.custom_handicap is None
