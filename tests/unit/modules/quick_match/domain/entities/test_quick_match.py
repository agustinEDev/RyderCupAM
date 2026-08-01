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
from src.modules.quick_match.domain.events.quick_match_participant_handicap_updated_event import (
    QuickMatchParticipantHandicapUpdatedEvent,
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
    InvalidAllowanceViolation,
    InvalidQuickMatchFormatViolation,
    InvalidQuickMatchStatusViolation,
    InvalidScorerConfigurationViolation,
    InvalidTeamAssignmentViolation,
    NotQuickMatchParticipantViolation,
    QuickMatchFullViolation,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
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


def _make_free_play_quick_match(scoring_format=ScoringFormat.STABLEFORD, **overrides):
    defaults = {
        "id": QuickMatchId.generate(),
        "creator_id": UserId(uuid4()),
        "golf_course_id": GolfCourseId(uuid4()),
        "match_format": None,
        "scoring_format": scoring_format,
    }
    defaults.update(overrides)
    return QuickMatch.create(**defaults)


def _registered(team=None):
    return QuickMatchParticipant.for_user(UserId(uuid4()), team=team)


def _guest(team=None):
    return QuickMatchParticipant.for_guest(first_name="Guest", last_name="Player", team=team)


class TestQuickMatchCreate:
    def test_create_sets_pending_status(self):
        qm = _make_quick_match()
        assert qm.status == QuickMatchStatus.PENDING

    def test_create_adds_creator_as_first_participant(self):
        qm = _make_quick_match()
        assert len(qm.participants) == 1
        assert qm.participants[0].participant_id == qm.creator_participant_id

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


class TestQuickMatchName:
    def test_create_without_name_defaults_to_none(self):
        qm = _make_quick_match()
        assert qm.name is None

    def test_create_with_name_stores_it(self):
        qm = _make_quick_match(name="Viernes con los del club")
        assert qm.name == "Viernes con los del club"

    def test_create_trims_surrounding_whitespace(self):
        qm = _make_quick_match(name="  Revancha  ")
        assert qm.name == "Revancha"

    def test_create_blank_name_normalizes_to_none(self):
        qm = _make_quick_match(name="   ")
        assert qm.name is None

    def test_create_rejects_name_over_max_length(self):
        with pytest.raises(ValueError, match="cannot exceed 100 characters"):
            _make_quick_match(name="a" * 101)

    def test_create_accepts_name_at_max_length(self):
        qm = _make_quick_match(name="a" * 100)
        assert qm.name == "a" * 100


class TestQuickMatchAddParticipant:
    def test_add_registered_participant_singles_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.clear_domain_events()
        other = _registered()
        qm.add_participant(other)

        assert qm.is_participant(other.participant_id)
        assert qm.is_roster_complete()
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchParticipantAddedEvent)

    def test_add_guest_participant_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        guest = _guest()
        qm.add_participant(guest)

        assert qm.is_participant(guest.participant_id)
        assert qm.find_participant(guest.participant_id).is_guest

    def test_add_participant_singles_rejects_team(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        with pytest.raises(InvalidTeamAssignmentViolation):
            qm.add_participant(_registered(team="A"))

    def test_add_participant_fourball_requires_team(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        with pytest.raises(InvalidTeamAssignmentViolation):
            qm.add_participant(_registered(team=None))

    def test_add_participant_fourball_fills_teams(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        qm.add_participant(_registered(team="A"))
        qm.add_participant(_registered(team="B"))
        qm.add_participant(_guest(team="B"))

        assert qm.is_roster_complete()
        assert qm._team_count("A") == 2
        assert qm._team_count("B") == 2

    def test_add_participant_team_full_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        qm.add_participant(_registered(team="A"))
        with pytest.raises(QuickMatchFullViolation):
            qm.add_participant(_registered(team="A"))

    def test_add_duplicate_participant_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        creator_participant = QuickMatchParticipant.for_user(qm.creator_id)
        with pytest.raises(DuplicateParticipantViolation):
            qm.add_participant(creator_participant)

    def test_add_participant_when_full_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        with pytest.raises(QuickMatchFullViolation):
            qm.add_participant(_registered())

    def test_add_participant_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        qm.start([qm.creator_participant_id])
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.add_participant(_registered())


class TestQuickMatchTeamRosters:
    def test_singles_falls_back_to_each_participant_as_a_side(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)

        rosters = qm.team_rosters()

        assert rosters == ({qm.creator_participant_id}, {other.participant_id})

    def test_fourball_derives_rosters_from_team_field(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        partner_a = _registered(team="A")
        opponent_b1 = _registered(team="B")
        opponent_b2 = _guest(team="B")
        qm.add_participant(partner_a)
        qm.add_participant(opponent_b1)
        qm.add_participant(opponent_b2)

        team_a_ids, team_b_ids = qm.team_rosters()

        assert team_a_ids == {qm.creator_participant_id, partner_a.participant_id}
        assert team_b_ids == {opponent_b1.participant_id, opponent_b2.participant_id}

    def test_returns_none_with_fewer_than_two_participants(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        assert qm.team_rosters() is None

    def test_incomplete_fourball_with_two_participants_on_same_team_returns_none(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        qm.add_participant(_registered(team="A"))

        assert qm.team_rosters() is None


class TestQuickMatchRemoveParticipant:
    def test_remove_participant_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        qm.clear_domain_events()

        qm.remove_participant(other.participant_id)

        assert not qm.is_participant(other.participant_id)
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchParticipantRemovedEvent)

    def test_remove_creator_raises(self):
        qm = _make_quick_match()
        with pytest.raises(CreatorCannotBeRemovedViolation):
            qm.remove_participant(qm.creator_participant_id)

    def test_remove_non_participant_raises(self):
        qm = _make_quick_match()
        with pytest.raises(NotQuickMatchParticipantViolation):
            qm.remove_participant(ParticipantId.generate())

    def test_remove_participant_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        qm.start([qm.creator_participant_id])
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.remove_participant(other.participant_id)


class TestQuickMatchSetParticipantHandicap:
    def test_set_registered_participant_handicap_sets_override(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        qm.clear_domain_events()

        qm.set_participant_handicap(other.participant_id, 12.3)

        updated = qm.find_participant(other.participant_id)
        assert updated.custom_handicap == 12.3
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchParticipantHandicapUpdatedEvent)

    def test_set_guest_participant_handicap_sets_manual_handicap(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        guest = _guest()
        qm.add_participant(guest)

        qm.set_participant_handicap(guest.participant_id, 24.0)

        assert qm.find_participant(guest.participant_id).handicap == 24.0

    def test_set_participant_handicap_none_clears_it(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        guest = _guest()
        qm.add_participant(guest)
        qm.set_participant_handicap(guest.participant_id, 24.0)

        qm.set_participant_handicap(guest.participant_id, None)

        assert qm.find_participant(guest.participant_id).handicap is None

    def test_set_handicap_preserves_other_participant_fields(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        other = _registered(team="B")
        qm.add_participant(other)

        qm.set_participant_handicap(other.participant_id, 5.0)

        updated = qm.find_participant(other.participant_id)
        assert updated.team == "B"
        assert updated.user_id == other.user_id

    def test_set_handicap_for_non_participant_raises(self):
        qm = _make_quick_match()
        with pytest.raises(NotQuickMatchParticipantViolation):
            qm.set_participant_handicap(ParticipantId.generate(), 10.0)

    def test_set_handicap_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        qm.start([qm.creator_participant_id])

        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.set_participant_handicap(other.participant_id, 10.0)

    def test_set_handicap_out_of_range_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        with pytest.raises(ValueError, match="custom_handicap debe estar entre"):
            qm.set_participant_handicap(other.participant_id, 99)


class TestQuickMatchStart:
    def test_start_with_complete_roster_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        qm.clear_domain_events()

        qm.start([qm.creator_participant_id])

        assert qm.status == QuickMatchStatus.IN_PROGRESS
        assert qm.scorer_ids == [qm.creator_participant_id]
        events = qm.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], QuickMatchStartedEvent)

    def test_start_with_incomplete_roster_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        with pytest.raises(IncompleteRosterViolation):
            qm.start([qm.creator_participant_id])

    def test_start_when_not_pending_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        qm.start([qm.creator_participant_id])
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.start([qm.creator_participant_id])

    def test_start_without_creator_in_scorers_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        other = _registered()
        qm.add_participant(other)
        with pytest.raises(InvalidScorerConfigurationViolation, match="creator"):
            qm.start([other.participant_id])

    def test_start_with_guest_as_scorer_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        qm.add_participant(_registered(team="A"))
        qm.add_participant(_registered(team="B"))
        guest = _guest(team="B")
        qm.add_participant(guest)
        with pytest.raises(InvalidScorerConfigurationViolation, match="not a registered"):
            qm.start([qm.creator_participant_id, guest.participant_id])

    def test_start_with_non_registered_scorer_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        with pytest.raises(
            InvalidScorerConfigurationViolation, match="not a registered participant"
        ):
            qm.start(
                [qm.creator_participant_id, ParticipantId.generate(), ParticipantId.generate()]
            )

    def test_start_with_duplicate_scorers_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        with pytest.raises(InvalidScorerConfigurationViolation, match="duplicates"):
            qm.start([qm.creator_participant_id, qm.creator_participant_id])


class TestQuickMatchComplete:
    def test_complete_from_in_progress_succeeds(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        qm.start([qm.creator_participant_id])
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
        qm.add_participant(_registered())
        qm.start([qm.creator_participant_id])
        qm.cancel()
        assert qm.status == QuickMatchStatus.CANCELLED

    def test_cancel_from_completed_raises(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        qm.add_participant(_registered())
        qm.start([qm.creator_participant_id])
        qm.complete()
        with pytest.raises(InvalidQuickMatchStatusViolation):
            qm.cancel()


class TestQuickMatchQueries:
    def test_capacity_singles(self):
        assert _make_quick_match(match_format=MatchFormat.SINGLES).capacity() == 2

    def test_capacity_fourball(self):
        assert _make_quick_match(match_format=MatchFormat.FOURBALL).capacity() == 4

    def test_registered_participants_excludes_guests(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        guest = _guest()
        qm.add_participant(guest)
        registered = qm.registered_participants()
        assert guest not in registered
        assert len(registered) == 1

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


class TestQuickMatchFormatExclusivity:
    def test_create_requires_exactly_one_format(self):
        with pytest.raises(InvalidQuickMatchFormatViolation):
            QuickMatch.create(
                id=QuickMatchId.generate(),
                creator_id=UserId(uuid4()),
                golf_course_id=GolfCourseId(uuid4()),
            )

    def test_create_rejects_both_formats_together(self):
        with pytest.raises(InvalidQuickMatchFormatViolation):
            QuickMatch.create(
                id=QuickMatchId.generate(),
                creator_id=UserId(uuid4()),
                golf_course_id=GolfCourseId(uuid4()),
                match_format=MatchFormat.SINGLES,
                scoring_format=ScoringFormat.MEDAL,
            )

    def test_reconstruct_requires_exactly_one_format(self):
        with pytest.raises(InvalidQuickMatchFormatViolation):
            QuickMatch.reconstruct(
                id=QuickMatchId.generate(),
                creator_id=UserId(uuid4()),
                golf_course_id=GolfCourseId(uuid4()),
                match_format=None,
                status=QuickMatchStatus.PENDING,
                participants=[],
            )


class TestQuickMatchFreePlay:
    def test_create_stableford_creator_has_no_team(self):
        qm = _make_free_play_quick_match(scoring_format=ScoringFormat.STABLEFORD)
        assert qm.match_format is None
        assert qm.scoring_format == ScoringFormat.STABLEFORD
        assert qm.participants[0].team is None

    def test_capacity_is_four(self):
        assert _make_free_play_quick_match().capacity() == 4

    def test_roster_is_always_complete_solo(self):
        qm = _make_free_play_quick_match()
        assert qm.is_roster_complete()

    def test_can_start_solo_with_only_creator(self):
        qm = _make_free_play_quick_match()
        qm.start([qm.creator_participant_id])
        assert qm.status == QuickMatchStatus.IN_PROGRESS

    def test_can_start_with_three_players(self):
        qm = _make_free_play_quick_match()
        qm.add_participant(_registered())
        qm.add_participant(_registered())
        qm.start([qm.creator_participant_id])
        assert qm.status == QuickMatchStatus.IN_PROGRESS

    def test_add_participant_rejects_team(self):
        qm = _make_free_play_quick_match(scoring_format=ScoringFormat.MEDAL)
        with pytest.raises(InvalidTeamAssignmentViolation):
            qm.add_participant(_registered(team="A"))

    def test_add_participant_up_to_four_then_full(self):
        qm = _make_free_play_quick_match()
        qm.add_participant(_registered())
        qm.add_participant(_registered())
        qm.add_participant(_registered())
        assert len(qm.participants) == 4
        with pytest.raises(QuickMatchFullViolation):
            qm.add_participant(_registered())


class TestQuickMatchAllowance:
    def test_default_allowance_singles(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES)
        assert qm.allowance_percentage is None
        assert qm.get_effective_allowance() == 100

    def test_default_allowance_fourball(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURBALL)
        assert qm.get_effective_allowance() == 90

    def test_default_allowance_foursomes(self):
        qm = _make_quick_match(match_format=MatchFormat.FOURSOMES)
        assert qm.get_effective_allowance() == 50

    def test_default_allowance_free_play(self):
        qm = _make_free_play_quick_match()
        assert qm.get_effective_allowance() == 95

    def test_custom_allowance_overrides_default(self):
        qm = _make_quick_match(match_format=MatchFormat.SINGLES, allowance_percentage=80)
        assert qm.allowance_percentage == 80
        assert qm.get_effective_allowance() == 80

    def test_rejects_allowance_not_multiple_of_five(self):
        with pytest.raises(InvalidAllowanceViolation):
            _make_quick_match(allowance_percentage=77)

    def test_rejects_allowance_out_of_range(self):
        with pytest.raises(InvalidAllowanceViolation):
            _make_quick_match(allowance_percentage=45)
