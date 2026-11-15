"""Tests para CompetitionPolicy - metodos de invitaciones."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationCompetitionStatusViolation,
    InvitationRateLimitViolation,
)
from src.modules.competition.domain.services.competition_policy import (
    MAX_INVITATIONS_PER_HOUR,
    CompetitionPolicy,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)


class TestCanSendInvitation:
    """Tests para CompetitionPolicy.can_send_invitation()."""

    def test_active_allows_send(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.ACTIVE)

    # I4 (#710, 24 sep): cerrada, no queda plaza. Una invitación enviada ahí
    # nadie podría aceptarla
    @pytest.mark.parametrize("status", [CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS])
    def test_closed_or_in_progress_does_not_send(self, status):
        with pytest.raises(InvitationCompetitionStatusViolation, match="plazas"):
            CompetitionPolicy.can_send_invitation(status)

    def test_draft_allows_send(self):
        """BE #319: invitar a la primera persona es lo que abre el torneo."""
        CompetitionPolicy.can_send_invitation(CompetitionStatus.DRAFT)

    def test_completed_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="COMPLETED"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.COMPLETED)

    def test_cancelled_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="CANCELLED"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.CANCELLED)


class TestInvitationOpensEnrollment:
    """Tests para CompetitionPolicy.invitation_opens_enrollment()."""

    def test_draft_opens(self):
        assert CompetitionPolicy.invitation_opens_enrollment(CompetitionStatus.DRAFT) is True

    @pytest.mark.parametrize(
        "status",
        [
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
            CompetitionStatus.COMPLETED,
            CompetitionStatus.CANCELLED,
        ],
    )
    def test_the_rest_do_not(self, status):
        """Solo se abre lo que esta por abrir: nada de reabrir un torneo."""
        assert CompetitionPolicy.invitation_opens_enrollment(status) is False


class TestCanAcceptInvitation:
    """Tests para CompetitionPolicy.can_accept_invitation()."""

    def test_active_allows_accept(self):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.ACTIVE)

    # I3 (#710, 24 sep): con los equipos hechos, entrar descuadra los partidos
    @pytest.mark.parametrize("status", [CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS])
    def test_closed_or_in_progress_does_not_accept(self, status):
        with pytest.raises(InvitationCompetitionStatusViolation, match="plazas"):
            CompetitionPolicy.can_accept_invitation(status)

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


class TestInvitationRateCeiling:
    """El freno tiene su propio numero y deja de crecer con el cupo.

    El limite efectivo es `min(cupo, MAX_INVITATIONS_PER_HOUR)`: las competiciones
    pequenas conservan su freno de siempre y las grandes topan en la constante. Los
    cupos de 300 de aqui son hipoteticos —hoy el maximo es 100— y estan para fijar
    la regla antes de que el cupo suba.
    """

    def test_ceiling_is_one_hundred(self):
        assert MAX_INVITATIONS_PER_HOUR == 100

    def test_large_competition_passes_below_the_ceiling(self):
        comp_id = CompetitionId(uuid4())
        CompetitionPolicy.validate_invitation_rate(99, 300, comp_id)

    def test_large_competition_raises_at_the_ceiling(self):
        """Con un cupo de 300 el freno saltaria en 100, no en 300."""
        comp_id = CompetitionId(uuid4())
        with pytest.raises(InvitationRateLimitViolation):
            CompetitionPolicy.validate_invitation_rate(100, 300, comp_id)

    def test_message_states_the_effective_limit(self):
        """El mensaje debe citar el limite que se aplica, no el cupo."""
        comp_id = CompetitionId(uuid4())
        with pytest.raises(InvitationRateLimitViolation, match="100/100"):
            CompetitionPolicy.validate_invitation_rate(100, 300, comp_id)

    def test_small_competition_keeps_its_own_limit(self):
        """Un cupo de 12 sigue frenando en 12: el techo no afloja nada."""
        comp_id = CompetitionId(uuid4())
        CompetitionPolicy.validate_invitation_rate(11, 12, comp_id)
        with pytest.raises(InvitationRateLimitViolation, match="12/12"):
            CompetitionPolicy.validate_invitation_rate(12, 12, comp_id)
