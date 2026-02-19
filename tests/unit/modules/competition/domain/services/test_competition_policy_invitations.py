"""Tests para CompetitionPolicy - metodos de invitaciones."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationCompetitionStatusViolation,
    InvitationRateLimitViolation,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)


class TestCanSendInvitation:
    """Tests para CompetitionPolicy.can_send_invitation()."""

    def test_active_allows_send(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.ACTIVE)

    def test_closed_allows_send(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.CLOSED)

    def test_in_progress_allows_send(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.IN_PROGRESS)

    def test_draft_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="DRAFT"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.DRAFT)

    def test_completed_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="COMPLETED"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.COMPLETED)

    def test_cancelled_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="CANCELLED"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.CANCELLED)


class TestCanAcceptInvitation:
    """Tests para CompetitionPolicy.can_accept_invitation()."""

    def test_active_allows_accept(self):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.ACTIVE)

    def test_closed_allows_accept(self):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.CLOSED)

    def test_in_progress_allows_accept(self):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.IN_PROGRESS)

    def test_draft_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="DRAFT"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.DRAFT)

    def test_completed_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="COMPLETED"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.COMPLETED)

    def test_cancelled_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="CANCELLED"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.CANCELLED)


class TestValidateInvitationRate:
    """Tests para CompetitionPolicy.validate_invitation_rate()."""

    def test_under_limit_passes(self):
        comp_id = CompetitionId(uuid4())
        CompetitionPolicy.validate_invitation_rate(10, 24, comp_id)

    def test_zero_invitations_passes(self):
        comp_id = CompetitionId(uuid4())
        CompetitionPolicy.validate_invitation_rate(0, 24, comp_id)

    def test_one_below_limit_passes(self):
        comp_id = CompetitionId(uuid4())
        CompetitionPolicy.validate_invitation_rate(23, 24, comp_id)

    def test_at_limit_raises(self):
        comp_id = CompetitionId(uuid4())
        with pytest.raises(InvitationRateLimitViolation, match="24/24"):
            CompetitionPolicy.validate_invitation_rate(24, 24, comp_id)

    def test_above_limit_raises(self):
        comp_id = CompetitionId(uuid4())
        with pytest.raises(InvitationRateLimitViolation, match="30/24"):
            CompetitionPolicy.validate_invitation_rate(30, 24, comp_id)

    def test_small_competition_limit(self):
        """Competicion de 4 jugadores, limite es 4 por hora."""
        comp_id = CompetitionId(uuid4())
        CompetitionPolicy.validate_invitation_rate(3, 4, comp_id)
        with pytest.raises(InvitationRateLimitViolation):
            CompetitionPolicy.validate_invitation_rate(4, 4, comp_id)
