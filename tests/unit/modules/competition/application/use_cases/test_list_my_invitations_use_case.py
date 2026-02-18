"""Tests para ListMyInvitationsUseCase."""

from datetime import date

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_my_invitations_use_case import (
    ListMyInvitationsUseCase,
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


class TestListMyInvitationsUseCase:
    """Tests para listar invitaciones del usuario actual."""

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

    async def test_list_empty_invitations(self, comp_uow, user_uow):
        """Usuario sin invitaciones retorna lista vacia."""
        user = await self._create_user(user_uow, email="lonely@test.com")

        uc = ListMyInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(user_id=str(user.id.value))

        assert result.total_count == 0
        assert result.invitations == []
        assert result.page == 1
        assert result.limit == 20

    async def test_list_invitations_by_email(self, comp_uow, user_uow):
        """Lista invitaciones encontradas por email del invitee."""
        creator = await self._create_user(user_uow, email="creator@test.com", first_name="Creator", last_name="Boss")
        invitee = await self._create_user(user_uow, email="invitee@test.com", first_name="Invitee", last_name="Player")
        created = await self._create_active_competition(comp_uow, creator.id)

        await self._add_invitation(
            comp_uow, created.id, creator.id, "invitee@test.com", invitee.id
        )

        uc = ListMyInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(user_id=str(invitee.id.value))

        assert result.total_count == 1
        assert len(result.invitations) == 1
        assert result.invitations[0].invitee_email == "invitee@test.com"
        assert result.invitations[0].competition_name == "Test Cup"

    async def test_list_multiple_invitations(self, comp_uow, user_uow):
        """Lista multiples invitaciones para un usuario."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        comp1 = await self._create_active_competition(comp_uow, creator.id, name="Cup 1")
        comp2 = await self._create_active_competition(comp_uow, creator.id, name="Cup 2")

        await self._add_invitation(comp_uow, comp1.id, creator.id, "invitee@test.com", invitee.id)
        await self._add_invitation(comp_uow, comp2.id, creator.id, "invitee@test.com", invitee.id)

        uc = ListMyInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(user_id=str(invitee.id.value))

        assert result.total_count == 2

    async def test_list_with_status_filter(self, comp_uow, user_uow):
        """Filtrar invitaciones por status."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        await self._add_invitation(
            comp_uow, created.id, creator.id, "invitee@test.com", invitee.id
        )

        uc = ListMyInvitationsUseCase(comp_uow, user_uow)
        # Filtrar por PENDING
        result = await uc.execute(user_id=str(invitee.id.value), status_filter="PENDING")
        assert result.total_count == 1

        # Filtrar por ACCEPTED (ninguna)
        result = await uc.execute(user_id=str(invitee.id.value), status_filter="ACCEPTED")
        assert result.total_count == 0

    async def test_list_with_pagination(self, comp_uow, user_uow):
        """Paginacion funciona correctamente."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")

        for i in range(5):
            comp = await self._create_active_competition(comp_uow, creator.id, name=f"Cup {i}")
            await self._add_invitation(comp_uow, comp.id, creator.id, "invitee@test.com", invitee.id)

        uc = ListMyInvitationsUseCase(comp_uow, user_uow)
        # Page 1, limit 2
        result = await uc.execute(user_id=str(invitee.id.value), page=1, limit=2)
        assert result.total_count == 5
        assert len(result.invitations) == 2
        assert result.page == 1
        assert result.limit == 2

    async def test_deduplicates_email_and_user_id_results(self, comp_uow, user_uow):
        """No duplica invitaciones encontradas por email y por user_id."""
        creator = await self._create_user(user_uow, email="creator@test.com")
        invitee = await self._create_user(user_uow, email="invitee@test.com")
        created = await self._create_active_competition(comp_uow, creator.id)

        # Invitacion con email Y user_id (encontrada por ambas busquedas)
        await self._add_invitation(
            comp_uow, created.id, creator.id, "invitee@test.com", invitee.id
        )

        uc = ListMyInvitationsUseCase(comp_uow, user_uow)
        result = await uc.execute(user_id=str(invitee.id.value))

        # Debe ser 1, no 2 (deduplicado)
        assert result.total_count == 1
