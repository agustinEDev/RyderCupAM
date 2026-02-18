"""Tests para Invitation Entity."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.invitation import (
    INVITATION_EXPIRATION_DAYS,
    MAX_PERSONAL_MESSAGE_LENGTH,
    Invitation,
)
from src.modules.competition.domain.events.invitation_created_event import (
    InvitationCreatedEvent,
)
from src.modules.competition.domain.events.invitation_declined_event import (
    InvitationDeclinedEvent,
)
from src.modules.competition.domain.exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
    InvitationExpiredViolation,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import (
    InvitationStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId

# ==========================================================================
# Fixtures helpers
# ==========================================================================

def _make_invitation(**overrides):
    """Helper para crear invitaciones con valores por defecto."""
    defaults = {
        "id": InvitationId.generate(),
        "competition_id": CompetitionId(uuid4()),
        "inviter_id": UserId(uuid4()),
        "invitee_email": "player@example.com",
        "invitee_user_id": None,
        "personal_message": None,
    }
    defaults.update(overrides)
    return Invitation.create(**defaults)


def _make_expired_invitation(**overrides):
    """Helper para crear invitaciones expiradas (reconstruidas)."""
    defaults = {
        "id": InvitationId.generate(),
        "competition_id": CompetitionId(uuid4()),
        "inviter_id": UserId(uuid4()),
        "invitee_email": "expired@example.com",
        "status": InvitationStatus.PENDING,
        "expires_at": datetime.now() - timedelta(days=1),
        "created_at": datetime.now() - timedelta(days=8),
        "updated_at": datetime.now() - timedelta(days=8),
    }
    defaults.update(overrides)
    return Invitation.reconstruct(**defaults)


# ==========================================================================
# Creation Tests
# ==========================================================================

class TestInvitationCreate:
    """Tests para el factory method create."""

    def test_create_sets_pending_status(self):
        invitation = _make_invitation()
        assert invitation.status == InvitationStatus.PENDING

    def test_create_sets_expiration(self):
        before = datetime.now()
        invitation = _make_invitation()
        after = datetime.now()
        expected_min = before + timedelta(days=INVITATION_EXPIRATION_DAYS)
        expected_max = after + timedelta(days=INVITATION_EXPIRATION_DAYS)
        assert expected_min <= invitation.expires_at <= expected_max

    def test_create_sets_timestamps(self):
        before = datetime.now()
        invitation = _make_invitation()
        assert invitation.created_at >= before
        assert invitation.updated_at >= before

    def test_create_stores_email_normalized(self):
        invitation = _make_invitation(invitee_email="  Player@Example.COM  ")
        assert invitation.invitee_email == "player@example.com"

    def test_create_with_invitee_user_id(self):
        user_id = UserId(uuid4())
        invitation = _make_invitation(invitee_user_id=user_id)
        assert invitation.invitee_user_id == user_id

    def test_create_with_personal_message(self):
        invitation = _make_invitation(personal_message="Join my tournament!")
        assert invitation.personal_message == "Join my tournament!"

    def test_create_without_personal_message(self):
        invitation = _make_invitation()
        assert invitation.personal_message is None

    def test_create_emits_invitation_created_event(self):
        invitation = _make_invitation()
        events = invitation.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], InvitationCreatedEvent)

    def test_create_event_has_correct_fields(self):
        comp_id = CompetitionId(uuid4())
        inviter_id = UserId(uuid4())
        invitation = _make_invitation(
            competition_id=comp_id,
            inviter_id=inviter_id,
            invitee_email="test@test.com",
        )
        event = invitation.get_domain_events()[0]
        assert event.competition_id == str(comp_id)
        assert event.inviter_id == str(inviter_id)
        assert event.invitee_email == "test@test.com"

    def test_create_responded_at_is_none(self):
        invitation = _make_invitation()
        assert invitation.responded_at is None


class TestInvitationCreateValidation:
    """Tests para validaciones en la creacion."""

    def test_empty_email_raises(self):
        with pytest.raises(ValueError, match="invitee_email no puede estar vacio"):
            _make_invitation(invitee_email="")

    def test_whitespace_email_raises(self):
        with pytest.raises(ValueError, match="invitee_email no puede estar vacio"):
            _make_invitation(invitee_email="   ")

    def test_message_too_long_raises(self):
        long_message = "x" * (MAX_PERSONAL_MESSAGE_LENGTH + 1)
        with pytest.raises(ValueError, match="personal_message no puede exceder"):
            _make_invitation(personal_message=long_message)

    def test_message_at_max_length_is_valid(self):
        message = "x" * MAX_PERSONAL_MESSAGE_LENGTH
        invitation = _make_invitation(personal_message=message)
        assert len(invitation.personal_message) == MAX_PERSONAL_MESSAGE_LENGTH


# ==========================================================================
# Reconstruct Tests
# ==========================================================================

class TestInvitationReconstruct:
    """Tests para el factory method reconstruct."""

    def test_reconstruct_preserves_all_fields(self):
        inv_id = InvitationId.generate()
        comp_id = CompetitionId(uuid4())
        inviter = UserId(uuid4())
        invitee = UserId(uuid4())
        now = datetime.now()

        invitation = Invitation.reconstruct(
            id=inv_id,
            competition_id=comp_id,
            inviter_id=inviter,
            invitee_email="test@test.com",
            status=InvitationStatus.ACCEPTED,
            expires_at=now + timedelta(days=7),
            invitee_user_id=invitee,
            personal_message="Hello",
            responded_at=now,
            created_at=now - timedelta(days=1),
            updated_at=now,
        )

        assert invitation.id == inv_id
        assert invitation.competition_id == comp_id
        assert invitation.inviter_id == inviter
        assert invitation.invitee_user_id == invitee
        assert invitation.status == InvitationStatus.ACCEPTED
        assert invitation.personal_message == "Hello"

    def test_reconstruct_does_not_emit_events(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.PENDING,
            expires_at=datetime.now() + timedelta(days=7),
        )
        assert invitation.get_domain_events() == []


# ==========================================================================
# Properties Tests
# ==========================================================================

class TestInvitationProperties:
    """Tests para las properties de lectura."""

    def test_id_property(self):
        inv_id = InvitationId.generate()
        invitation = _make_invitation(id=inv_id)
        assert invitation.id == inv_id

    def test_competition_id_property(self):
        comp_id = CompetitionId(uuid4())
        invitation = _make_invitation(competition_id=comp_id)
        assert invitation.competition_id == comp_id

    def test_inviter_id_property(self):
        inviter = UserId(uuid4())
        invitation = _make_invitation(inviter_id=inviter)
        assert invitation.inviter_id == inviter

    def test_invitee_email_property(self):
        invitation = _make_invitation(invitee_email="test@example.com")
        assert invitation.invitee_email == "test@example.com"


# ==========================================================================
# Query Methods Tests
# ==========================================================================

class TestInvitationQueries:
    """Tests para metodos de consulta."""

    def test_is_expired_when_not_expired(self):
        invitation = _make_invitation()
        assert not invitation.is_expired()

    def test_is_expired_when_expired(self):
        invitation = _make_expired_invitation()
        assert invitation.is_expired()

    def test_is_pending_when_pending(self):
        invitation = _make_invitation()
        assert invitation.is_pending()

    def test_is_pending_when_accepted(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.ACCEPTED,
            expires_at=datetime.now() + timedelta(days=7),
        )
        assert not invitation.is_pending()

    def test_is_for_user_matches(self):
        user_id = UserId(uuid4())
        invitation = _make_invitation(invitee_user_id=user_id)
        assert invitation.is_for_user(user_id)

    def test_is_for_user_does_not_match_different_user(self):
        invitation = _make_invitation(invitee_user_id=UserId(uuid4()))
        assert not invitation.is_for_user(UserId(uuid4()))

    def test_is_for_user_false_when_no_user_id(self):
        invitation = _make_invitation()
        assert not invitation.is_for_user(UserId(uuid4()))

    def test_is_for_email_matches(self):
        invitation = _make_invitation(invitee_email="test@example.com")
        assert invitation.is_for_email("test@example.com")

    def test_is_for_email_case_insensitive(self):
        invitation = _make_invitation(invitee_email="test@example.com")
        assert invitation.is_for_email("TEST@EXAMPLE.COM")

    def test_is_for_email_trims_whitespace(self):
        invitation = _make_invitation(invitee_email="test@example.com")
        assert invitation.is_for_email("  test@example.com  ")

    def test_is_for_email_does_not_match_different(self):
        invitation = _make_invitation(invitee_email="test@example.com")
        assert not invitation.is_for_email("other@example.com")


# ==========================================================================
# Command Methods Tests
# ==========================================================================

class TestInvitationAccept:
    """Tests para el metodo accept()."""

    def test_accept_changes_status_to_accepted(self):
        invitation = _make_invitation()
        invitation.accept()
        assert invitation.status == InvitationStatus.ACCEPTED

    def test_accept_sets_responded_at(self):
        invitation = _make_invitation()
        before = datetime.now()
        invitation.accept()
        assert invitation.responded_at is not None
        assert invitation.responded_at >= before

    def test_accept_updates_updated_at(self):
        invitation = _make_invitation()
        old_updated = invitation.updated_at
        invitation.accept()
        assert invitation.updated_at >= old_updated

    def test_accept_expired_raises_and_transitions(self):
        invitation = _make_expired_invitation()
        with pytest.raises(InvitationExpiredViolation):
            invitation.accept()
        assert invitation.status == InvitationStatus.EXPIRED

    def test_accept_already_accepted_raises(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.ACCEPTED,
            expires_at=datetime.now() + timedelta(days=7),
        )
        with pytest.raises(InvalidInvitationStatusViolation):
            invitation.accept()

    def test_accept_declined_raises(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.DECLINED,
            expires_at=datetime.now() + timedelta(days=7),
        )
        with pytest.raises(InvalidInvitationStatusViolation):
            invitation.accept()


class TestInvitationDecline:
    """Tests para el metodo decline()."""

    def test_decline_changes_status_to_declined(self):
        invitation = _make_invitation()
        invitation.decline()
        assert invitation.status == InvitationStatus.DECLINED

    def test_decline_sets_responded_at(self):
        invitation = _make_invitation()
        invitation.decline()
        assert invitation.responded_at is not None

    def test_decline_emits_declined_event(self):
        invitation = _make_invitation()
        invitation.clear_domain_events()
        invitation.decline()
        events = invitation.get_domain_events()
        declined_events = [e for e in events if isinstance(e, InvitationDeclinedEvent)]
        assert len(declined_events) == 1

    def test_decline_event_has_correct_fields(self):
        comp_id = CompetitionId(uuid4())
        invitee_id = UserId(uuid4())
        invitation = _make_invitation(
            competition_id=comp_id,
            invitee_user_id=invitee_id,
        )
        invitation.clear_domain_events()
        invitation.decline()
        event = invitation.get_domain_events()[0]
        assert event.competition_id == str(comp_id)
        assert event.invitee_user_id == str(invitee_id)

    def test_decline_expired_raises(self):
        invitation = _make_expired_invitation()
        with pytest.raises(InvitationExpiredViolation):
            invitation.decline()

    def test_decline_already_declined_raises(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.DECLINED,
            expires_at=datetime.now() + timedelta(days=7),
        )
        with pytest.raises(InvalidInvitationStatusViolation):
            invitation.decline()


class TestInvitationCheckExpiration:
    """Tests para check_expiration()."""

    def test_check_expiration_transitions_pending_to_expired(self):
        invitation = _make_expired_invitation()
        invitation.check_expiration()
        assert invitation.status == InvitationStatus.EXPIRED

    def test_check_expiration_does_nothing_if_not_expired(self):
        invitation = _make_invitation()
        invitation.check_expiration()
        assert invitation.status == InvitationStatus.PENDING

    def test_check_expiration_does_nothing_for_accepted(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.ACCEPTED,
            expires_at=datetime.now() - timedelta(days=1),
        )
        invitation.check_expiration()
        assert invitation.status == InvitationStatus.ACCEPTED

    def test_check_expiration_does_nothing_for_declined(self):
        invitation = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=CompetitionId(uuid4()),
            inviter_id=UserId(uuid4()),
            invitee_email="test@test.com",
            status=InvitationStatus.DECLINED,
            expires_at=datetime.now() - timedelta(days=1),
        )
        invitation.check_expiration()
        assert invitation.status == InvitationStatus.DECLINED


# ==========================================================================
# Domain Events Tests
# ==========================================================================

class TestInvitationDomainEvents:
    """Tests para el manejo de domain events."""

    def test_get_domain_events_returns_copy(self):
        invitation = _make_invitation()
        events1 = invitation.get_domain_events()
        events2 = invitation.get_domain_events()
        assert events1 == events2
        assert events1 is not events2

    def test_clear_domain_events(self):
        invitation = _make_invitation()
        assert len(invitation.get_domain_events()) > 0
        invitation.clear_domain_events()
        assert invitation.get_domain_events() == []


# ==========================================================================
# Special Methods Tests
# ==========================================================================

class TestInvitationSpecialMethods:
    """Tests para __str__, __eq__, __hash__."""

    def test_str_representation(self):
        invitation = _make_invitation(invitee_email="test@test.com")
        result = str(invitation)
        assert "test@test.com" in result
        assert "PENDING" in result

    def test_eq_same_id(self):
        inv_id = InvitationId.generate()
        inv1 = _make_invitation(id=inv_id)
        inv2 = _make_invitation(id=inv_id)
        assert inv1 == inv2

    def test_eq_different_id(self):
        inv1 = _make_invitation()
        inv2 = _make_invitation()
        assert inv1 != inv2

    def test_eq_different_type(self):
        invitation = _make_invitation()
        assert invitation != "not-an-invitation"

    def test_hash_same_id(self):
        inv_id = InvitationId.generate()
        inv1 = _make_invitation(id=inv_id)
        inv2 = _make_invitation(id=inv_id)
        assert hash(inv1) == hash(inv2)

    def test_usable_in_set(self):
        inv_id = InvitationId.generate()
        inv1 = _make_invitation(id=inv_id)
        inv2 = _make_invitation(id=inv_id)
        assert len({inv1, inv2}) == 1
