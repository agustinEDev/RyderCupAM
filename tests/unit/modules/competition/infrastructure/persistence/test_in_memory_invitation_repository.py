"""Tests para InMemoryInvitationRepository."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import (
    InvitationStatus,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_invitation_repository import (
    InMemoryInvitationRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


def _make_invitation(
    invitee_email="test@test.com",
    competition_id=None,
    inviter_id=None,
    invitee_user_id=None,
    status=InvitationStatus.PENDING,
):
    """Helper para crear invitaciones con reconstruccion."""
    return Invitation.reconstruct(
        id=InvitationId.generate(),
        competition_id=competition_id or CompetitionId(uuid4()),
        inviter_id=inviter_id or UserId(uuid4()),
        invitee_email=invitee_email,
        invitee_user_id=invitee_user_id,
        status=status,
        expires_at=datetime.now() + timedelta(days=7),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestInMemoryInvitationRepositoryAdd:
    """Tests para add()."""

    async def test_add_and_find_by_id(self):
        repo = InMemoryInvitationRepository()
        invitation = _make_invitation()
        await repo.add(invitation)
        found = await repo.find_by_id(invitation.id)
        assert found is not None
        assert found.id == invitation.id

    async def test_find_by_id_returns_none_for_nonexistent(self):
        repo = InMemoryInvitationRepository()
        found = await repo.find_by_id(InvitationId.generate())
        assert found is None


class TestInMemoryInvitationRepositoryUpdate:
    """Tests para update()."""

    async def test_update_existing(self):
        repo = InMemoryInvitationRepository()
        invitation = _make_invitation()
        await repo.add(invitation)
        invitation.accept()
        await repo.update(invitation)
        found = await repo.find_by_id(invitation.id)
        assert found.status == InvitationStatus.ACCEPTED

    async def test_update_nonexistent_does_nothing(self):
        repo = InMemoryInvitationRepository()
        invitation = _make_invitation()
        await repo.update(invitation)
        found = await repo.find_by_id(invitation.id)
        assert found is None


class TestInMemoryInvitationRepositoryFindByCompetition:
    """Tests para find_by_competition()."""

    async def test_find_by_competition_returns_matches(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv1 = _make_invitation(invitee_email="a@test.com", competition_id=comp_id)
        inv2 = _make_invitation(invitee_email="b@test.com", competition_id=comp_id)
        inv3 = _make_invitation(invitee_email="c@test.com")  # Different competition
        await repo.add(inv1)
        await repo.add(inv2)
        await repo.add(inv3)

        results = await repo.find_by_competition(comp_id)
        assert len(results) == 2

    async def test_find_by_competition_with_status_filter(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        pending = _make_invitation(invitee_email="a@test.com", competition_id=comp_id)
        accepted = _make_invitation(
            invitee_email="b@test.com",
            competition_id=comp_id,
            status=InvitationStatus.ACCEPTED,
        )
        await repo.add(pending)
        await repo.add(accepted)

        results = await repo.find_by_competition(comp_id, status=InvitationStatus.PENDING)
        assert len(results) == 1
        assert results[0].status == InvitationStatus.PENDING

    async def test_find_by_competition_with_limit_offset(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        for i in range(5):
            inv = _make_invitation(invitee_email=f"player{i}@test.com", competition_id=comp_id)
            await repo.add(inv)

        results = await repo.find_by_competition(comp_id, limit=2, offset=1)
        assert len(results) == 2


class TestInMemoryInvitationRepositoryFindByEmail:
    """Tests para find_by_invitee_email()."""

    async def test_find_by_email(self):
        repo = InMemoryInvitationRepository()
        inv = _make_invitation(invitee_email="test@example.com")
        await repo.add(inv)

        results = await repo.find_by_invitee_email("test@example.com")
        assert len(results) == 1

    async def test_find_by_email_normalizes(self):
        repo = InMemoryInvitationRepository()
        inv = _make_invitation(invitee_email="test@example.com")
        await repo.add(inv)

        results = await repo.find_by_invitee_email("  TEST@EXAMPLE.COM  ")
        assert len(results) == 1

    async def test_find_by_email_with_status_filter(self):
        repo = InMemoryInvitationRepository()
        pending = _make_invitation(invitee_email="test@example.com")
        accepted = _make_invitation(
            invitee_email="test@example.com",
            status=InvitationStatus.ACCEPTED,
        )
        await repo.add(pending)
        await repo.add(accepted)

        results = await repo.find_by_invitee_email("test@example.com", status=InvitationStatus.PENDING)
        assert len(results) == 1


class TestInMemoryInvitationRepositoryFindByUserId:
    """Tests para find_by_invitee_user_id()."""

    async def test_find_by_user_id(self):
        repo = InMemoryInvitationRepository()
        user_id = UserId(uuid4())
        inv = _make_invitation(invitee_email="test@test.com", invitee_user_id=user_id)
        await repo.add(inv)

        results = await repo.find_by_invitee_user_id(user_id)
        assert len(results) == 1

    async def test_find_by_user_id_does_not_match_different(self):
        repo = InMemoryInvitationRepository()
        user_id = UserId(uuid4())
        inv = _make_invitation(invitee_email="test@test.com", invitee_user_id=user_id)
        await repo.add(inv)

        results = await repo.find_by_invitee_user_id(UserId(uuid4()))
        assert len(results) == 0


class TestInMemoryInvitationRepositoryFindPending:
    """Tests para find_pending_by_email_and_competition()."""

    async def test_find_pending_returns_match(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv = _make_invitation(invitee_email="test@test.com", competition_id=comp_id)
        await repo.add(inv)

        result = await repo.find_pending_by_email_and_competition("test@test.com", comp_id)
        assert result is not None
        assert result.id == inv.id

    async def test_find_pending_returns_none_for_accepted(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv = _make_invitation(
            invitee_email="test@test.com",
            competition_id=comp_id,
            status=InvitationStatus.ACCEPTED,
        )
        await repo.add(inv)

        result = await repo.find_pending_by_email_and_competition("test@test.com", comp_id)
        assert result is None

    async def test_find_pending_normalizes_email(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv = _make_invitation(invitee_email="test@test.com", competition_id=comp_id)
        await repo.add(inv)

        result = await repo.find_pending_by_email_and_competition("  TEST@TEST.COM  ", comp_id)
        assert result is not None

    async def test_find_pending_returns_none_for_different_competition(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv = _make_invitation(invitee_email="test@test.com", competition_id=comp_id)
        await repo.add(inv)

        result = await repo.find_pending_by_email_and_competition("test@test.com", CompetitionId(uuid4()))
        assert result is None


class TestInMemoryInvitationRepositoryCounting:
    """Tests para count_by_competition() y count_by_invitee()."""

    async def test_count_by_competition(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv1 = _make_invitation(invitee_email="a@test.com", competition_id=comp_id)
        inv2 = _make_invitation(invitee_email="b@test.com", competition_id=comp_id)
        await repo.add(inv1)
        await repo.add(inv2)

        count = await repo.count_by_competition(comp_id)
        assert count == 2

    async def test_count_by_competition_with_status(self):
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())
        inv1 = _make_invitation(invitee_email="a@test.com", competition_id=comp_id)
        inv2 = _make_invitation(
            invitee_email="b@test.com",
            competition_id=comp_id,
            status=InvitationStatus.ACCEPTED,
        )
        await repo.add(inv1)
        await repo.add(inv2)

        count = await repo.count_by_competition(comp_id, status=InvitationStatus.PENDING)
        assert count == 1

    async def test_count_by_competition_with_since_filter(self):
        """Filtro 'since' excluye invitaciones antiguas."""
        repo = InMemoryInvitationRepository()
        comp_id = CompetitionId(uuid4())

        # Invitacion reciente (hace 30 min)
        recent = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=comp_id,
            inviter_id=UserId(uuid4()),
            invitee_email="recent@test.com",
            status=InvitationStatus.PENDING,
            expires_at=datetime.now() + timedelta(days=7),
            created_at=datetime.now() - timedelta(minutes=30),
            updated_at=datetime.now(),
        )

        # Invitacion antigua (hace 2 horas)
        old = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=comp_id,
            inviter_id=UserId(uuid4()),
            invitee_email="old@test.com",
            status=InvitationStatus.PENDING,
            expires_at=datetime.now() + timedelta(days=7),
            created_at=datetime.now() - timedelta(hours=2),
            updated_at=datetime.now(),
        )

        await repo.add(recent)
        await repo.add(old)

        # Sin filtro: 2
        count_all = await repo.count_by_competition(comp_id)
        assert count_all == 2

        # Con filtro ultima hora: solo 1
        one_hour_ago = datetime.now() - timedelta(hours=1)
        count_recent = await repo.count_by_competition(comp_id, since=one_hour_ago)
        assert count_recent == 1

    async def test_count_by_invitee_email(self):
        repo = InMemoryInvitationRepository()
        inv = _make_invitation(invitee_email="test@test.com")
        await repo.add(inv)

        count = await repo.count_by_invitee(email="test@test.com")
        assert count == 1

    async def test_count_by_invitee_user_id(self):
        repo = InMemoryInvitationRepository()
        user_id = UserId(uuid4())
        inv = _make_invitation(invitee_email="test@test.com", invitee_user_id=user_id)
        await repo.add(inv)

        count = await repo.count_by_invitee(user_id=user_id)
        assert count == 1

    async def test_count_by_invitee_with_status(self):
        repo = InMemoryInvitationRepository()
        user_id = UserId(uuid4())
        inv1 = _make_invitation(invitee_email="test@test.com", invitee_user_id=user_id)
        inv2 = _make_invitation(
            invitee_email="test@test.com",
            invitee_user_id=user_id,
            status=InvitationStatus.DECLINED,
        )
        await repo.add(inv1)
        await repo.add(inv2)

        count = await repo.count_by_invitee(user_id=user_id, status=InvitationStatus.PENDING)
        assert count == 1
