"""Tests para Domain Events de Invitation."""

import pytest

from src.modules.competition.domain.events.invitation_accepted_event import (
    InvitationAcceptedEvent,
)
from src.modules.competition.domain.events.invitation_created_event import (
    InvitationCreatedEvent,
)
from src.modules.competition.domain.events.invitation_declined_event import (
    InvitationDeclinedEvent,
)
from src.shared.domain.events.domain_event import DomainEvent


class TestInvitationCreatedEvent:
    """Tests para InvitationCreatedEvent."""

    def test_is_domain_event(self):
        event = InvitationCreatedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            inviter_id="user-1",
            invitee_email="test@test.com",
        )
        assert isinstance(event, DomainEvent)

    def test_stores_all_fields(self):
        event = InvitationCreatedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            inviter_id="user-1",
            invitee_email="test@test.com",
        )
        assert event.invitation_id == "inv-1"
        assert event.competition_id == "comp-1"
        assert event.inviter_id == "user-1"
        assert event.invitee_email == "test@test.com"

    def test_is_frozen(self):
        event = InvitationCreatedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            inviter_id="user-1",
            invitee_email="test@test.com",
        )
        with pytest.raises(AttributeError):
            event.invitation_id = "changed"


class TestInvitationAcceptedEvent:
    """Tests para InvitationAcceptedEvent."""

    def test_is_domain_event(self):
        event = InvitationAcceptedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            invitee_user_id="user-2",
        )
        assert isinstance(event, DomainEvent)

    def test_stores_all_fields(self):
        event = InvitationAcceptedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            invitee_user_id="user-2",
        )
        assert event.invitation_id == "inv-1"
        assert event.competition_id == "comp-1"
        assert event.invitee_user_id == "user-2"


class TestInvitationDeclinedEvent:
    """Tests para InvitationDeclinedEvent."""

    def test_is_domain_event(self):
        event = InvitationDeclinedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            invitee_user_id="user-2",
        )
        assert isinstance(event, DomainEvent)

    def test_stores_all_fields(self):
        event = InvitationDeclinedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            invitee_user_id="user-2",
        )
        assert event.invitation_id == "inv-1"
        assert event.competition_id == "comp-1"
        assert event.invitee_user_id == "user-2"

    def test_invitee_user_id_can_be_empty_for_unregistered(self):
        event = InvitationDeclinedEvent(
            invitation_id="inv-1",
            competition_id="comp-1",
            invitee_user_id="",
        )
        assert event.invitee_user_id == ""
