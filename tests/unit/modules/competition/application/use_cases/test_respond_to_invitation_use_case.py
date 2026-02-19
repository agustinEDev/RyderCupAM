"""Tests para RespondToInvitationUseCase."""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
)
from src.modules.competition.application.exceptions import (
    InvitationNotFoundError,
    NotInviteeError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import (
    InvitationStatus,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)

pytestmark = pytest.mark.asyncio


class TestRespondToInvitationUseCase:
    """Tests para responder a una invitacion."""

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

    async def _create_active_competition(self, comp_uow, creator_id, max_players=24):
        create_uc = CreateCompetitionUseCase(comp_uow)
        request = CreateCompetitionRequestDTO(
            name="Test Cup",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=max_players,
        )
        created = await create_uc.execute(request, creator_id)

        async with comp_uow:
            competition = await comp_uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await comp_uow.competitions.update(competition)
            await comp_uow.commit()

        return created

    async def _create_pending_invitation(self, comp_uow, competition_id, inviter_id, invitee_user_id, invitee_email):
        """Helper: crea una invitacion PENDING en el repo."""
        invitation = Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(competition_id),
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            invitee_user_id=invitee_user_id,
        )
        async with comp_uow:
            await comp_uow.invitations.add(invitation)
            await comp_uow.commit()
        return invitation

    async def test_accept_invitation_successfully(self, comp_uow, user_uow):
        """Happy path: aceptar invitacion crea enrollment."""
        creator = await self._create_user(user_uow, email="creator@test.com", first_name="Creator", last_name="Boss")
        invitee = await self._create_user(user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="ACCEPT",
        )
        result = await uc.execute(request)

        assert result.status == "ACCEPTED"
        assert result.enrollment_id is not None
        assert result.inviter_name == "Creator Boss"
        assert result.invitee_name == "Invitee Player"

    async def test_decline_invitation_successfully(self, comp_uow, user_uow):
        """Happy path: rechazar invitacion."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="DECLINE",
        )
        result = await uc.execute(request)

        assert result.status == "DECLINED"
        assert result.enrollment_id is None

    async def test_should_raise_invitation_not_found(self, comp_uow, user_uow):
        """Invitacion inexistente lanza InvitationNotFoundError."""
        invitee = await self._create_user(user_uow, email="invitee@test.com")

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=uuid4(),
            user_id=invitee.id.value,
            action="ACCEPT",
        )

        with pytest.raises(InvitationNotFoundError):
            await uc.execute(request)

    async def test_should_raise_not_invitee(self, comp_uow, user_uow):
        """Usuario que no es invitee lanza NotInviteeError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=other.id.value,
            action="ACCEPT",
        )

        with pytest.raises(NotInviteeError):
            await uc.execute(request)

    async def test_should_raise_invalid_status_for_already_accepted(self, comp_uow, user_uow):
        """Invitacion ya aceptada lanza InvalidInvitationStatusViolation."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        # Crear invitacion ya ACCEPTED
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(created.id),
            inviter_id=creator.id,
            invitee_email="invitee@test.com",
            invitee_user_id=invitee.id,
            status=InvitationStatus.ACCEPTED,
            expires_at=datetime.now() + timedelta(days=7),
            responded_at=datetime.now(),
        )
        async with comp_uow:
            await comp_uow.invitations.add(invitation)
            await comp_uow.commit()

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="ACCEPT",
        )

        with pytest.raises(InvalidInvitationStatusViolation):
            await uc.execute(request)

    async def test_should_raise_invalid_action(self, comp_uow, user_uow):
        """Accion invalida lanza ValueError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        invitation = await self._create_pending_invitation(
            comp_uow, created.id, creator.id, invitee.id, "invitee@test.com"
        )

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="INVALID",
        )

        with pytest.raises(ValueError, match="Invalid action"):
            await uc.execute(request)

    async def test_accept_by_email_match(self, comp_uow, user_uow):
        """Invitee puede responder si el email coincide (sin invitee_user_id)."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        # Invitacion sin invitee_user_id (solo email)
        invitation = Invitation.create(
            id=InvitationId.generate(),
            competition_id=CompetitionId(created.id),
            inviter_id=creator.id,
            invitee_email="invitee@test.com",
            invitee_user_id=None,
        )
        async with comp_uow:
            await comp_uow.invitations.add(invitation)
            await comp_uow.commit()

        uc = RespondToInvitationUseCase(comp_uow, user_uow)
        request = RespondInvitationRequestDTO(
            invitation_id=invitation.id.value,
            user_id=invitee.id.value,
            action="ACCEPT",
        )
        result = await uc.execute(request)
        assert result.status == "ACCEPTED"
        assert result.enrollment_id is not None
