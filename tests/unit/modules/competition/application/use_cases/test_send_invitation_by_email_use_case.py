"""Tests para SendInvitationByEmailUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    SendInvitationByEmailRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    DuplicateInvitationViolation,
    InvitationRateLimitViolation,
    SelfInvitationViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)

pytestmark = pytest.mark.asyncio


class TestSendInvitationByEmailUseCase:
    """Tests para enviar invitacion por email."""

    @pytest.fixture
    def comp_uow(self):
        return CompetitionInMemoryUoW()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(self, user_uow, email="user@test.com", first_name="Test", last_name="User"):
        user = User.create(
            first_name=first_name,
            last_name=last_name,
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def _create_active_competition(self, comp_uow, creator_id):
        create_uc = CreateCompetitionUseCase(comp_uow)
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=24,
        )
        created = await create_uc.execute(request, creator_id)

        async with comp_uow:
            competition = await comp_uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await comp_uow.competitions.update(competition)
            await comp_uow.commit()

        return created

    async def test_should_send_invitation_to_registered_user(self, comp_uow, user_uow):
        """Happy path: enviar invitacion a un email de usuario registrado."""
        creator = await self._create_user(user_uow, email="creator@test.com", first_name="Creator", last_name="Boss")
        invitee = await self._create_user(user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="invitee@test.com",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        assert result.invitee_email == "invitee@test.com"
        assert result.invitee_user_id == invitee.id.value
        assert result.invitee_name == "Invitee Player"

    async def test_should_send_invitation_to_unregistered_email(self, comp_uow, user_uow):
        """Happy path: invitacion a email no registrado (invitee_user_id=None)."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="unregistered@test.com",
        )
        result = await uc.execute(request)

        assert result.status == "PENDING"
        assert result.invitee_email == "unregistered@test.com"
        assert result.invitee_user_id is None
        assert result.invitee_name is None

    async def test_should_raise_competition_not_found(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=uuid4(),
            inviter_id=creator.id.value,
            invitee_email="test@test.com",
        )

        with pytest.raises(CompetitionNotFoundError):
            await uc.execute(request)

    async def test_should_raise_not_creator(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=other.id.value,
            invitee_email="someone@test.com",
        )

        with pytest.raises(NotCompetitionCreatorError):
            await uc.execute(request)

    async def test_should_raise_self_invitation(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="creator@test.com",
        )

        with pytest.raises(SelfInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_already_enrolled(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(created.id),
            user_id=invitee.id,
        )
        async with comp_uow:
            await comp_uow.enrollments.add(enrollment)
            await comp_uow.commit()

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="invitee@test.com",
        )

        with pytest.raises(AlreadyEnrolledInvitationViolation):
            await uc.execute(request)

    async def test_should_raise_duplicate_invitation(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="unregistered@test.com",
        )

        await uc.execute(request)

        with pytest.raises(DuplicateInvitationViolation):
            await uc.execute(request)

    async def test_should_send_with_personal_message(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="new@test.com",
            personal_message="Welcome!",
        )
        result = await uc.execute(request)
        assert result.personal_message == "Welcome!"

    async def test_should_raise_rate_limit_when_max_players_reached(self, comp_uow, user_uow):
        """Exceder max_players invitaciones por hora lanza InvitationRateLimitViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)
        competition_id = CompetitionId(created.id)

        # Crear 24 invitaciones (max_players=24) directamente en repo
        for i in range(24):
            inv = Invitation.create(
                id=InvitationId.generate(),
                competition_id=competition_id,
                inviter_id=creator.id,
                invitee_email=f"player{i}@test.com",
            )
            async with comp_uow:
                await comp_uow.invitations.add(inv)
                await comp_uow.commit()

        # La invitacion 25 debe fallar por rate limit
        uc = SendInvitationByEmailUseCase(comp_uow, user_uow)
        request = SendInvitationByEmailRequestDTO(
            competition_id=created.id,
            inviter_id=creator.id.value,
            invitee_email="extra@test.com",
        )

        with pytest.raises(InvitationRateLimitViolation):
            await uc.execute(request)
