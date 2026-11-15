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

    @pytest.mark.parametrize("stroke_play", [False, True])
    def test_active_allows_send(self, stroke_play):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.ACTIVE, stroke_play=stroke_play)

    # B-02 (15 nov 2026, deshace I4 de #710): el organizador invita también con la
    # inscripción cerrada, hasta que empieza
    def test_closed_allows_send_in_a_ryder(self):
        CompetitionPolicy.can_send_invitation(CompetitionStatus.CLOSED, stroke_play=False)

    # P1: un stroke play cerrado no, porque nadie podría aceptarla
    def test_closed_stroke_play_does_not_send(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="plazas"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.CLOSED, stroke_play=True)

    @pytest.mark.parametrize("stroke_play", [False, True])
    def test_in_progress_does_not_send(self, stroke_play):
        with pytest.raises(InvitationCompetitionStatusViolation, match="plazas"):
            CompetitionPolicy.can_send_invitation(
                CompetitionStatus.IN_PROGRESS, stroke_play=stroke_play
            )

    def test_draft_allows_send(self):
        """BE #319: invitar a la primera persona es lo que abre el torneo."""
        CompetitionPolicy.can_send_invitation(CompetitionStatus.DRAFT, stroke_play=False)

    def test_completed_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="COMPLETED"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.COMPLETED, stroke_play=False)

    def test_cancelled_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="CANCELLED"):
            CompetitionPolicy.can_send_invitation(CompetitionStatus.CANCELLED, stroke_play=False)


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

    @pytest.mark.parametrize("stroke_play", [False, True])
    def test_active_allows_accept(self, stroke_play):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.ACTIVE, stroke_play=stroke_play)

    # B-02 (15 nov 2026, deshace I3 de #710): cerrada se entra, con sitio
    def test_closed_allows_accept_in_a_ryder(self):
        CompetitionPolicy.can_accept_invitation(CompetitionStatus.CLOSED, stroke_play=False)

    # P1: en un stroke play cerrado hay que reabrir
    def test_closed_stroke_play_does_not_accept(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="reabrir"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.CLOSED, stroke_play=True)

    @pytest.mark.parametrize("stroke_play", [False, True])
    def test_in_progress_does_not_accept(self, stroke_play):
        with pytest.raises(InvitationCompetitionStatusViolation, match="plazas"):
            CompetitionPolicy.can_accept_invitation(
                CompetitionStatus.IN_PROGRESS, stroke_play=stroke_play
            )

    def test_draft_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="DRAFT"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.DRAFT, stroke_play=False)

    def test_completed_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="COMPLETED"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.COMPLETED, stroke_play=False)

    def test_cancelled_raises(self):
        with pytest.raises(InvitationCompetitionStatusViolation, match="CANCELLED"):
            CompetitionPolicy.can_accept_invitation(CompetitionStatus.CANCELLED, stroke_play=False)


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
