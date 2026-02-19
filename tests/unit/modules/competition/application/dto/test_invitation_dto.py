"""Tests para Invitation DTOs."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    PaginatedInvitationResponseDTO,
    RespondInvitationRequestDTO,
    RespondInvitationResponseDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)


class TestSendInvitationByUserIdRequestDTO:
    """Tests para SendInvitationByUserIdRequestDTO."""

    def test_valid_creation(self):
        dto = SendInvitationByUserIdRequestDTO(
            competition_id=uuid4(),
            inviter_id=uuid4(),
            invitee_user_id=uuid4(),
        )
        assert dto.personal_message is None

    def test_with_personal_message(self):
        dto = SendInvitationByUserIdRequestDTO(
            competition_id=uuid4(),
            inviter_id=uuid4(),
            invitee_user_id=uuid4(),
            personal_message="Join my tournament!",
        )
        assert dto.personal_message == "Join my tournament!"

    def test_message_too_long_raises(self):
        with pytest.raises(ValidationError):
            SendInvitationByUserIdRequestDTO(
                competition_id=uuid4(),
                inviter_id=uuid4(),
                invitee_user_id=uuid4(),
                personal_message="x" * 501,
            )

    def test_message_at_max_length(self):
        dto = SendInvitationByUserIdRequestDTO(
            competition_id=uuid4(),
            inviter_id=uuid4(),
            invitee_user_id=uuid4(),
            personal_message="x" * 500,
        )
        assert len(dto.personal_message) == 500


class TestSendInvitationByEmailRequestDTO:
    """Tests para SendInvitationByEmailRequestDTO."""

    def test_valid_creation(self):
        dto = SendInvitationByEmailRequestDTO(
            competition_id=uuid4(),
            inviter_id=uuid4(),
            invitee_email="test@example.com",
        )
        assert dto.invitee_email == "test@example.com"

    def test_with_personal_message(self):
        dto = SendInvitationByEmailRequestDTO(
            competition_id=uuid4(),
            inviter_id=uuid4(),
            invitee_email="test@example.com",
            personal_message="Join us!",
        )
        assert dto.personal_message == "Join us!"

    def test_message_too_long_raises(self):
        with pytest.raises(ValidationError):
            SendInvitationByEmailRequestDTO(
                competition_id=uuid4(),
                inviter_id=uuid4(),
                invitee_email="test@example.com",
                personal_message="x" * 501,
            )


class TestRespondInvitationRequestDTO:
    """Tests para RespondInvitationRequestDTO."""

    def test_accept_action(self):
        dto = RespondInvitationRequestDTO(
            invitation_id=uuid4(),
            user_id=uuid4(),
            action="ACCEPT",
        )
        assert dto.action == "ACCEPT"

    def test_decline_action(self):
        dto = RespondInvitationRequestDTO(
            invitation_id=uuid4(),
            user_id=uuid4(),
            action="DECLINE",
        )
        assert dto.action == "DECLINE"


class TestInvitationResponseDTO:
    """Tests para InvitationResponseDTO."""

    def test_full_creation(self):
        now = datetime.now()
        uid = uuid4()
        dto = InvitationResponseDTO(
            id=uuid4(),
            competition_id=uuid4(),
            competition_name="Test Cup",
            inviter_id=uuid4(),
            inviter_name="John Doe",
            invitee_email="test@test.com",
            invitee_user_id=uid,
            invitee_name="Jane Doe",
            status="PENDING",
            personal_message="Join!",
            expires_at=now,
            responded_at=None,
            created_at=now,
            updated_at=now,
        )
        assert dto.invitee_name == "Jane Doe"
        assert dto.invitee_user_id == uid

    def test_minimal_creation(self):
        now = datetime.now()
        dto = InvitationResponseDTO(
            id=uuid4(),
            competition_id=uuid4(),
            competition_name="Test Cup",
            inviter_id=uuid4(),
            inviter_name="John Doe",
            invitee_email="test@test.com",
            status="PENDING",
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        assert dto.invitee_user_id is None
        assert dto.invitee_name is None
        assert dto.personal_message is None
        assert dto.responded_at is None


class TestRespondInvitationResponseDTO:
    """Tests para RespondInvitationResponseDTO."""

    def test_with_enrollment_id(self):
        now = datetime.now()
        eid = uuid4()
        dto = RespondInvitationResponseDTO(
            id=uuid4(),
            competition_id=uuid4(),
            competition_name="Test Cup",
            inviter_id=uuid4(),
            inviter_name="John Doe",
            invitee_email="test@test.com",
            status="ACCEPTED",
            expires_at=now,
            created_at=now,
            updated_at=now,
            enrollment_id=eid,
        )
        assert dto.enrollment_id == eid

    def test_without_enrollment_id(self):
        now = datetime.now()
        dto = RespondInvitationResponseDTO(
            id=uuid4(),
            competition_id=uuid4(),
            competition_name="Test Cup",
            inviter_id=uuid4(),
            inviter_name="John Doe",
            invitee_email="test@test.com",
            status="DECLINED",
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        assert dto.enrollment_id is None


class TestPaginatedInvitationResponseDTO:
    """Tests para PaginatedInvitationResponseDTO."""

    def test_empty_list(self):
        dto = PaginatedInvitationResponseDTO(
            invitations=[],
            total_count=0,
            page=1,
            limit=20,
        )
        assert dto.invitations == []
        assert dto.total_count == 0

    def test_with_invitations(self):
        now = datetime.now()
        inv_dto = InvitationResponseDTO(
            id=uuid4(),
            competition_id=uuid4(),
            competition_name="Test Cup",
            inviter_id=uuid4(),
            inviter_name="John Doe",
            invitee_email="test@test.com",
            status="PENDING",
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        dto = PaginatedInvitationResponseDTO(
            invitations=[inv_dto],
            total_count=1,
            page=1,
            limit=20,
        )
        assert len(dto.invitations) == 1
        assert dto.total_count == 1
        assert dto.page == 1
        assert dto.limit == 20
