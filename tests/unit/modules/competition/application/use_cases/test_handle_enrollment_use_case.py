"""Tests para HandleEnrollmentUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    CompetitionNotFoundError,
    EnrollmentNotFoundError,
    HandleEnrollmentUseCase,
    NotCreatorError,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class TestHandleEnrollmentUseCase:
    """Suite de tests para el caso de uso HandleEnrollmentUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        return UserId(uuid4())

    @pytest.fixture
    def other_user_id(self) -> UserId:
        return UserId(uuid4())

    async def _create_active_competition(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, max_players: int = 24
    ):
        """Helper: crea y activa una competición."""
        create_uc = CreateCompetitionUseCase(uow)
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=max_players,
        )
        created = await create_uc.execute(request, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        return created

    async def _create_requested_enrollment(
        self, uow: InMemoryUnitOfWork, competition_id, user_id: UserId
    ) -> Enrollment:
        """Helper: crea un enrollment en estado REQUESTED."""
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(competition_id),
            user_id=user_id,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()
        return enrollment

    async def test_should_approve_enrollment_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Given: Un enrollment en estado REQUESTED
        When: El creador lo aprueba
        Then: El enrollment pasa a APPROVED
        """
        created = await self._create_active_competition(uow, creator_id)
        enrollment = await self._create_requested_enrollment(uow, created.id, other_user_id)

        use_case = HandleEnrollmentUseCase(uow)
        request = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment.id.value,
            action="APPROVE",
        )
        response = await use_case.execute(request, creator_id)

        assert response.status == "APPROVED"
        assert response.user_id == other_user_id.value

    async def test_should_reject_enrollment_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Given: Un enrollment en estado REQUESTED
        When: El creador lo rechaza
        Then: El enrollment pasa a REJECTED
        """
        created = await self._create_active_competition(uow, creator_id)
        enrollment = await self._create_requested_enrollment(uow, created.id, other_user_id)

        use_case = HandleEnrollmentUseCase(uow)
        request = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment.id.value,
            action="REJECT",
        )
        response = await use_case.execute(request, creator_id)

        assert response.status == "REJECTED"
        assert response.user_id == other_user_id.value

    async def test_should_raise_enrollment_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un enrollment_id que no existe
        When: Se intenta manejar
        Then: Se lanza EnrollmentNotFoundError
        """
        use_case = HandleEnrollmentUseCase(uow)
        request = HandleEnrollmentRequestDTO(
            enrollment_id=uuid4(),
            action="APPROVE",
        )

        with pytest.raises(EnrollmentNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_not_creator_error(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Given: Un enrollment válido
        When: Un usuario que NO es el creador intenta aprobar
        Then: Se lanza NotCreatorError
        """
        created = await self._create_active_competition(uow, creator_id)
        enrollment = await self._create_requested_enrollment(uow, created.id, other_user_id)

        use_case = HandleEnrollmentUseCase(uow)
        request = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment.id.value,
            action="APPROVE",
        )

        with pytest.raises(NotCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_raise_validation_error_for_invalid_action(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Given: Un enrollment válido
        When: Se crea el DTO con una acción inválida
        Then: Se lanza ValidationError en el DTO (Pydantic)
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HandleEnrollmentRequestDTO(
                enrollment_id=uuid4(),
                action="INVALID",
            )

    async def test_should_raise_competition_full_when_approving_at_capacity(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición con max_players=2 y ya 2 aprobados (creator + 1)
        When: El creador intenta aprobar otro enrollment
        Then: Se lanza CompetitionFullViolation
        """
        # max_players=2, el creador ya ocupa 1 plaza (auto-enroll)
        created = await self._create_active_competition(uow, creator_id, max_players=2)

        # Crear un segundo jugador y aprobarlo para llenar la competición
        player2_id = UserId(uuid4())
        enrollment2 = await self._create_requested_enrollment(uow, created.id, player2_id)

        use_case = HandleEnrollmentUseCase(uow)
        approve_request = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment2.id.value,
            action="APPROVE",
        )
        # Aprobar al segundo jugador (ahora hay 2 de 2)
        response = await use_case.execute(approve_request, creator_id)
        assert response.status == "APPROVED"

        # Crear un tercer jugador e intentar aprobar
        player3_id = UserId(uuid4())
        enrollment3 = await self._create_requested_enrollment(uow, created.id, player3_id)

        approve_request3 = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment3.id.value,
            action="APPROVE",
        )

        with pytest.raises(CompetitionFullViolation):
            await use_case.execute(approve_request3, creator_id)

    async def test_should_allow_reject_when_competition_is_full(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición llena (2/2)
        When: El creador rechaza un enrollment pendiente
        Then: Se rechaza correctamente (reject no verifica capacidad)
        """
        created = await self._create_active_competition(uow, creator_id, max_players=2)

        # Llenar la competición: aprobar a un segundo jugador
        player2_id = UserId(uuid4())
        enrollment2 = await self._create_requested_enrollment(uow, created.id, player2_id)

        use_case = HandleEnrollmentUseCase(uow)
        approve_req = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment2.id.value,
            action="APPROVE",
        )
        await use_case.execute(approve_req, creator_id)

        # Crear un tercer jugador pendiente
        player3_id = UserId(uuid4())
        enrollment3 = await self._create_requested_enrollment(uow, created.id, player3_id)

        # Rechazar debería funcionar aunque la competición esté llena
        reject_req = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment3.id.value,
            action="REJECT",
        )
        response = await use_case.execute(reject_req, creator_id)
        assert response.status == "REJECTED"

    async def test_should_raise_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un enrollment cuya competición no existe
        When: Se intenta manejar
        Then: Se lanza CompetitionNotFoundError
        """
        # Crear enrollment con competition_id que no existe
        fake_comp_id = CompetitionId(uuid4())
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=fake_comp_id,
            user_id=UserId(uuid4()),
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()

        use_case = HandleEnrollmentUseCase(uow)
        request = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment.id.value,
            action="APPROVE",
        )

        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request, creator_id)
