"""Tests para ScoringCoverageService."""

from uuid import uuid4

from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId


def _registered():
    return QuickMatchParticipant.for_user(UserId(uuid4()))


def _guest():
    return QuickMatchParticipant.for_guest(first_name="Guest", last_name="Player")


class TestScoringCoverageService:
    def setup_method(self):
        self.service = ScoringCoverageService()

    def test_single_scorer_covers_everyone(self):
        creator = _registered()
        others = [_registered(), _guest(), _guest()]
        participants = [creator, *others]

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[creator.participant_id],
            creator_participant_id=creator.participant_id,
        )

        assert set(assignments[creator.participant_id]) == {p.participant_id for p in participants}

    def test_two_scorers_split_evenly_four_players(self):
        creator = _registered()
        scorer_b = _registered()
        non_scorers = [_guest(), _guest()]
        participants = [creator, scorer_b, *non_scorers]

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[creator.participant_id, scorer_b.participant_id],
            creator_participant_id=creator.participant_id,
        )

        assert len(assignments[creator.participant_id]) == 2
        assert len(assignments[scorer_b.participant_id]) == 2
        covered = assignments[creator.participant_id] + assignments[scorer_b.participant_id]
        assert set(covered) == {p.participant_id for p in participants}

    def test_three_scorers_four_players_creator_absorbs_remainder(self):
        creator = _registered()
        scorer_b = _registered()
        scorer_c = _registered()
        non_scorer = _guest()
        participants = [creator, scorer_b, scorer_c, non_scorer]

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[creator.participant_id, scorer_b.participant_id, scorer_c.participant_id],
            creator_participant_id=creator.participant_id,
        )

        assert len(assignments[creator.participant_id]) == 2
        assert non_scorer.participant_id in assignments[creator.participant_id]
        assert len(assignments[scorer_b.participant_id]) == 1
        assert len(assignments[scorer_c.participant_id]) == 1

    def test_four_scorers_each_covers_only_self(self):
        creator = _registered()
        others = [_registered(), _registered(), _registered()]
        participants = [creator, *others]
        scorer_ids = [creator.participant_id, *[p.participant_id for p in others]]

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=scorer_ids,
            creator_participant_id=creator.participant_id,
        )

        for p in participants:
            assert assignments[p.participant_id] == [p.participant_id]

    def test_scorer_always_covers_self(self):
        creator = _registered()
        participants = [creator]

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[creator.participant_id],
            creator_participant_id=creator.participant_id,
        )

        assert assignments[creator.participant_id] == [creator.participant_id]
