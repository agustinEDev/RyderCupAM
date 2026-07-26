"""Tests para QuickMatch Entity."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.events.quick_match_cancelled_event import (
    QuickMatchCancelledEvent,
)
from src.modules.quick_match.domain.events.quick_match_completed_event import (
    QuickMatchCompletedEvent,
)
from src.modules.quick_match.domain.events.quick_match_created_event import (
    QuickMatchCreatedEvent,
)
from src.modules.quick_match.domain.events.quick_match_participant_added_event import (
    QuickMatchParticipantAddedEvent,
)
from src.modules.quick_match.domain.events.quick_match_participant_removed_event import (
    QuickMatchParticipantRemovedEvent,
)
from src.modules.quick_match.domain.events.quick_match_started_event import (
    QuickMatchStartedEvent,
)
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    CreatorCannotBeRemovedViolation,
    DuplicateParticipantViolation,
    IncompleteRosterViolation,
    InvalidQuickMatchStatusViolation,
    InvalidTeamAssignmentViolation,
    NotQuickMatchParticipantViolation,
    QuickMatchFullViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.value_objects.user_id import UserId


def _make_quick_match(match_format=MatchFormat.SINGLES, **overrides):
    defaults = {
        "id": QuickMatchId.generate(),
        "creator_id": UserId(uuid4()),
        "golf_course_id": GolfCourseId(uuid4()),
        "match_format": match_format,
    }
    defaults.update(overrides)
    return QuickMatch.create(**defaults)


class TestQuickMatchCreate:
    def test_create_sets_pending_status(self):
        qm = _make_quick_match()
        assert qm.status == QuickMatchStatus.PENDING

    def test_create_adds_creator_as_first_participant(self):
        qm = _make_quick_match()
        assert len(qm.participants) == 1
        assert qm.participants[0].user_id == qm.creator_id

    def test_create_singles_creator_has_no_team(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        assert qm.participants[0].team is None

    def test_create_fourball_creator_is_team_a(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        assert qm.participants[0].team == "A"

    def test_create_emits_created_and_participant_added_events(self):
        qm = _make_quick_match()
        events = qm.get_domain_events()
        assert any(isinstance(e, QuickMatchCreatedEvent) for e in events)
        assert any(isinstance(e, QuickMatchParticipantAddedEvent) for e in events)


class TestQuickMatchAddParticipant:
    def test_add_participant_singles_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.clear_domain_events()
        other = UserId(uuid4())
        qm.add_participant(other)

        assert qm.is_participant(other)
        assert qm.is_roster_complete()
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchParticipantAddedEvent)

    def test_add_participant_singles_rejects_team(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        with pytest.raises(InvalidTeamAssignmentViolation):
            qm.add_participant(UserId(uuid4()), team="A")

    def test_add_participant_fourball_requires_team(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        with pytest.raises(InvalidTeamAssignmentViolation):
            qm.add_participant(UserId(uuid4()), team=None)

    def test_add_participant_fourball_fills_teams(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        qm.add_participant(UserId(uuid4()), team="A")
        qm.add_participant(UserId(uuid4()), team="B")
        qm.add_participant(UserId(uuid4()), team="B")

        assert qm.is_roster_complete()
        assert qm._team_count("A") == 2
        assert qm._team_count("B") == 2

    def test_add_participant_team_full_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        qm.add_participant(UserId(uuid4()), team="A")
        with pytest.raises(QuickMatchFullViolation):
            qm.add_participant(UserId(uuid4()), team="A")

    def test_add_duplicate_participant_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        with pytest.raises(DuplicateParticipantViolation):
            qm.add_participant(qm.creator_id)

    def test_add_participant_when_full_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        with pytest.raises(QuickMatchFullViolation):
            qm.add_participant(UserId(uuid4()))

    def test_add_participant_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        qm.start()
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.add_participant(UserId(uuid4()))


class TestQuickMatchRemoveParticipant:
    def test_remove_participant_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = UserId(uuid4())
        qm.add_participant(other)
        qm.clear_domain_events()

        qm.remove_participant(other)

        assert not qm.is_participant(other)
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchParticipantRemovedEvent)

    def test_remove_creator_raises(self):
        qm = _make_quick_match()
        with pytest.raises(CreatorCannotBeRemovedViolation):
            qm.remove_participant(qm.creator_id)

    def test_remove_non_participant_raises(self):
        qm = _make_quick_match()
        with pytest.raises(NotQuickMatchParticipantViolation):
            qm.remove_participant(UserId(uuid4()))

    def test_remove_participant_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = UserId(uuid4())
        qm.add_participant(other)
        qm.start()
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.remove_participant(other)


class TestQuickMatchStart:
    def test_start_with_complete_roster_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        qm.clear_domain_events()

        qm.start()

        assert qm.status == QuickMatchStatus.IN_PROGRESS
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchStartedEvent)

    def test_start_with_incomplete_roster_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        with pytest.raises(IncompleteRosterViolation):
            qm.start()

    def test_start_when_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        qm.start()
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.start()


class TestQuickMatchComplete:
    def test_complete_from_in_progress_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        qm.start()
        qm.clear_domain_events()

        qm.complete()

        assert qm.status == QuickMatchStatus.COMPLETED
        events = qm.get_domain_events()
        assert isinstance(events[0], QuickMatchCompletedEvent)

    def test_complete_from_pending_raises(self):
        qm = _make_quick_match()
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.complete()


class TestQuickMatchCancel:
    def test_cancel_from_pending_succeeds(self):
        qm = _make_quick_match()
        qm.clear_domain_events()
        qm.cancel()
        assert qm.status == QuickMatchStatus.CANCELLED
        assert isinstance(qm.get_domain_events()[0], QuickMatchCancelledEvent)

    def test_cancel_from_in_progress_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        qm.start()
        qm.cancel()
        assert qm.status == QuickMatchStatus.CANCELLED

    def test_cancel_from_completed_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(UserId(uuid4()))
        qm.start()
        qm.complete()
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.cancel()


class TestQuickMatchQueries:
    def test_capacity_singles(self):
        assert _make_quick_match(match_format=MatchFormat.SINGLES).capacity() == 2

    def test_capacity_fourball(self):
        assert _make_quick_match(match_format=MatchFormat.FOURBALL).capacity() == 4

    def test_reconstruct_does_not_emit_events(self):
        qm = QuickMatch.reconstruct(
            id=QuickMatchId.generate(),
            creator_id=UserId(uuid4()),
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
            status=QuickMatchStatus.PENDING,
            participants=[],
        )
        assert qm.get_domain_events() == []
