"""Tests para QuickMatchParticipant Value Object."""

from uuid import uuid4

import pytest

from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class TestQuickMatchParticipantForUser:
    def test_for_user_creates_with_no_team(self):
        user_id = UserId(uuid4())
        p = QuickMatchParticipant.for_user(user_id)
        assert p.team is None
        assert p.user_id == user_id
        assert not p.is_guest
        assert p.participant_id == ParticipantId(user_id.value)

    def test_for_user_creates_with_valid_team(self):
        p = QuickMatchParticipant.for_user(UserId(uuid4()), team="A")
        assert p.team == "A"

    def test_for_user_rejects_invalid_team(self):
        with pytest.raises(ValueError, match="team debe ser"):
            QuickMatchParticipant.for_user(UserId(uuid4()), team="C")

    def test_for_user_has_no_manual_fields(self):
        p = QuickMatchParticipant.for_user(UserId(uuid4()))
        assert p.first_name is None
        assert p.last_name is None
        assert p.handicap is None

    def test_for_user_defaults_to_no_tee_selected(self):
        p = QuickMatchParticipant.for_user(UserId(uuid4()))
        assert p.tee_category is None
        assert p.tee_gender is None

    def test_for_user_accepts_tee_selection(self):
        p = QuickMatchParticipant.for_user(
            UserId(uuid4()), tee_category=TeeCategory.AMATEUR, tee_gender=Gender.MALE
        )
        assert p.tee_category == TeeCategory.AMATEUR
        assert p.tee_gender == Gender.MALE


class TestQuickMatchParticipantForGuest:
    def test_for_guest_creates_without_user_id(self):
        p = QuickMatchParticipant.for_guest(first_name="Jane", last_name="Doe")
        assert p.is_guest
        assert p.user_id is None
        assert p.first_name == "Jane"
        assert p.last_name == "Doe"
        assert p.handicap is None

    def test_for_guest_accepts_optional_handicap(self):
        p = QuickMatchParticipant.for_guest(first_name="Jane", last_name="Doe", handicap=18.4)
        assert p.handicap == 18.4

    def test_for_guest_rejects_out_of_range_handicap(self):
        with pytest.raises(ValueError, match="handicap debe estar entre"):
            QuickMatchParticipant.for_guest(first_name="Jane", last_name="Doe", handicap=99)

    def test_for_guest_requires_first_name(self):
        with pytest.raises(ValueError, match="first_name"):
            QuickMatchParticipant.for_guest(first_name="", last_name="Doe")

    def test_for_guest_requires_last_name(self):
        with pytest.raises(ValueError, match="last_name"):
            QuickMatchParticipant.for_guest(first_name="Jane", last_name="")

    def test_for_guest_generates_unique_participant_id(self):
        a = QuickMatchParticipant.for_guest(first_name="Jane", last_name="Doe")
        b = QuickMatchParticipant.for_guest(first_name="Jane", last_name="Doe")
        assert a.participant_id != b.participant_id

    def test_for_guest_accepts_tee_selection(self):
        p = QuickMatchParticipant.for_guest(
            first_name="Jane",
            last_name="Doe",
            tee_category=TeeCategory.FORWARD,
            tee_gender=Gender.FEMALE,
        )
        assert p.tee_category == TeeCategory.FORWARD
        assert p.tee_gender == Gender.FEMALE


class TestQuickMatchParticipantEquality:
    def test_equality_by_participant_id_only(self):
        user_id = UserId(uuid4())
        a = QuickMatchParticipant.for_user(user_id, team="A")
        b = QuickMatchParticipant.for_user(user_id, team="B")
        assert a == b

    def test_hash_by_participant_id(self):
        user_id = UserId(uuid4())
        a = QuickMatchParticipant.for_user(user_id)
        assert hash(a) == hash(ParticipantId(user_id.value))
