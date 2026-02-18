"""Tests para ListCompetitionInvitationsUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)

pytestmark = pytest.mark.asyncio


class TestListCompetitionInvitationsUseCase:
    """Tests para listar invitaciones de una competicion."""

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

    async def _create_active_competition(self, comp_uow, creator_id, name="Test Cup"):
        create_uc = CreateCompetitionUseCase(comp_uow)
        request = CreateCompetitionRequestDTO(
            name=name,
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

    async def _add_invitation(self, comp_uow, competition_id, inviter_id, invitee_email, invitee_user_id=None):
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

    async def test_list_empty(self, comp_uow, user_uow):
        """Competition sin invitaciones retorna lista vacia."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(creator.id.value),
        )

        assert result.total_count == 0
        assert result.invitations == []

    async def test_list_invitations_as_creator(self, comp_uow, user_uow):
        """Creator puede listar invitaciones de su competicion."""
        creator = await self._create_user(user_uow, email="creator@test.com", first_name="Creator", last_name="Boss")
        created = await self._create_active_competition(comp_uow, creator.id)

        await self._add_invitation(comp_uow, created.id, creator.id, "player1@test.com")
        await self._add_invitation(comp_uow, created.id, creator.id, "player2@test.com")

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(creator.id.value),
        )

        assert result.total_count == 2
        assert len(result.invitations) == 2

    async def test_list_invitations_as_admin(self, comp_uow, user_uow):
        """Admin puede listar invitaciones de cualquier competicion."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        admin = await self._create_user(user_uow, email="admin@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        await self._add_invitation(comp_uow, created.id, creator.id, "player1@test.com")

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(admin.id.value),
            is_admin=True,
        )

        assert result.total_count == 1

    async def test_should_raise_competition_not_found(self, comp_uow, user_uow):
        creator = await self._create_user(user_uow, email="creator@test.com")

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)

        with pytest.raises(CompetitionNotFoundError):
            await uc.execute(
                competition_id=str(uuid4()),
                current_user_id=str(creator.id.value),
            )

    async def test_should_raise_not_creator(self, comp_uow, user_uow):
        """No-creator sin admin lanza NotCompetitionCreatorError."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        other = await self._create_user(user_uow, email="other@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)

        with pytest.raises(NotCompetitionCreatorError):
            await uc.execute(
                competition_id=str(created.id),
                current_user_id=str(other.id.value),
                is_admin=False,
            )

    async def test_list_with_status_filter(self, comp_uow, user_uow):
        """Filtrar por status funciona."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        await self._add_invitation(comp_uow, created.id, creator.id, "player1@test.com")

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)
        # PENDING (hay una)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(creator.id.value),
            status_filter="PENDING",
        )
        assert result.total_count == 1

        # ACCEPTED (ninguna)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(creator.id.value),
            status_filter="ACCEPTED",
        )
        assert result.total_count == 0

    async def test_list_with_pagination(self, comp_uow, user_uow):
        """Paginacion funciona correctamente."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        for i in range(5):
            await self._add_invitation(comp_uow, created.id, creator.id, f"player{i}@test.com")

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(creator.id.value),
            page=1,
            limit=2,
        )

        assert len(result.invitations) == 2
        assert result.page == 1
        assert result.limit == 2

    async def test_invitations_enriched_with_names(self, comp_uow, user_uow):
        """Las invitaciones incluyen inviter_name y competition_name."""
        creator = await self._create_user(user_uow, email="creator@test.com", first_name="John", last_name="Doe")
        created = await self._create_active_competition(comp_uow, creator.id, name="Champions Cup")

        await self._add_invitation(comp_uow, created.id, creator.id, "player@test.com")

        uc = ListCompetitionInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(
            competition_id=str(created.id),
            current_user_id=str(creator.id.value),
        )

        assert result.invitations[0].inviter_name == "John Doe"
        assert result.invitations[0].competition_name == "Champions Cup"
