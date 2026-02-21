"""Tests para Scoring Domain Events."""

from src.modules.competition.domain.events.scoring_events import (
    HoleScoreSubmittedEvent,
    MatchConcededEvent,
    ScorecardSubmittedEvent,
)
from src.shared.domain.events.domain_event import DomainEvent


class TestHoleScoreSubmittedEvent:
    def test_is_domain_event(self):
        event = HoleScoreSubmittedEvent(match_id="m1", hole_number=1, scorer_user_id="u1")
        assert isinstance(event, DomainEvent)

    def test_attributes(self):
        event = HoleScoreSubmittedEvent(match_id="m1", hole_number=5, scorer_user_id="u1")
        assert event.match_id == "m1"
        assert event.hole_number == 5
        assert event.scorer_user_id == "u1"

    def test_is_frozen(self):
        event = HoleScoreSubmittedEvent(match_id="m1", hole_number=1, scorer_user_id="u1")
        try:
            event.match_id = "m2"
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestScorecardSubmittedEvent:
    def test_is_domain_event(self):
        event = ScorecardSubmittedEvent(match_id="m1", user_id="u1", all_submitted=False)
        assert isinstance(event, DomainEvent)

    def test_attributes(self):
        event = ScorecardSubmittedEvent(match_id="m1", user_id="u1", all_submitted=True)
        assert event.match_id == "m1"
        assert event.user_id == "u1"
        assert event.all_submitted is True


class TestMatchConcededEvent:
    def test_is_domain_event(self):
        event = MatchConcededEvent(match_id="m1", conceding_team="A", reason=None)
        assert isinstance(event, DomainEvent)

    def test_attributes(self):
        event = MatchConcededEvent(match_id="m1", conceding_team="A", reason="Injury")
        assert event.match_id == "m1"
        assert event.conceding_team == "A"
        assert event.reason == "Injury"

    def test_reason_optional(self):
        event = MatchConcededEvent(match_id="m1", conceding_team="B", reason=None)
        assert event.reason is None
