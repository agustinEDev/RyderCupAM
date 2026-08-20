"""Tests para ScoringCoverageService."""

from uuid import uuid4

from src.modules.competition.domain.value_objects.match_format import MatchFormat
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


def _registered_on(team):
    return QuickMatchParticipant.for_user(UserId(uuid4()), team=team)


def _guest_on(team):
    return QuickMatchParticipant.for_guest(first_name="Guest", last_name="Player", team=team)


class TestFoursomesScoresCrossed:
    """
    En foursomes el bando juega UNA bola, asi que solo hay dos tarjetas y se
    anotan cruzadas, como en un 1 vs 1: cada anotador apunta las dos.
    """

    def setup_method(self):
        self.service = ScoringCoverageService()

    def test_each_scorer_covers_the_four_participants(self):
        me = _registered_on("A")
        partner = _registered_on("A")
        rival_one = _registered_on("B")
        rival_two = _guest_on("B")
        participants = [me, partner, rival_one, rival_two]
        everyone = {p.participant_id for p in participants}

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[me.participant_id, rival_one.participant_id],
            creator_participant_id=me.participant_id,
            match_format=MatchFormat.FOURSOMES,
        )

        # Cada uno anota los golpes de su bando y marca los del contrario.
        assert set(assignments[me.participant_id]) == everyone
        assert set(assignments[rival_one.participant_id]) == everyone

    def test_the_only_scorer_carries_both_balls(self):
        me = _registered_on("A")
        partner = _guest_on("A")
        rival_one = _guest_on("B")
        rival_two = _guest_on("B")
        participants = [me, partner, rival_one, rival_two]

        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[me.participant_id],
            creator_participant_id=me.participant_id,
            match_format=MatchFormat.FOURSOMES,
        )

        # Sin nadie enfrente, lleva las dos tarjetas: ninguna bola se queda sin
        # quien pueda anotarla.
        assert set(assignments[me.participant_id]) == {p.participant_id for p in participants}

    def test_a_scorer_covers_its_own_ball_even_with_a_rival_scorer(self):
        """
        La regresion que motiva el cruce: con anotador enfrente, el propio bando
        se quedaba sin nadie que pudiera anotarlo si ese rival no abria la app.
        """
        me = _registered_on("A")
        partner = _guest_on("A")
        rival_one = _registered_on("B")
        rival_two = _guest_on("B")

        assignments = self.service.compute_assignments(
            participants=[me, partner, rival_one, rival_two],
            scorer_ids=[me.participant_id, rival_one.participant_id],
            creator_participant_id=me.participant_id,
            match_format=MatchFormat.FOURSOMES,
        )

        assert me.participant_id in assignments[me.participant_id]
        assert partner.participant_id in assignments[me.participant_id]

    def test_two_scorers_on_the_same_side_both_carry_everything(self):
        me = _registered_on("A")
        partner = _registered_on("A")
        rival_one = _registered_on("B")
        rival_two = _guest_on("B")
        participants = [me, partner, rival_one, rival_two]
        everyone = {p.participant_id for p in participants}

        # Con anotador tambien enfrente: el caso que el test anterior no llegaba
        # a ejercitar, porque sin rival anotador caia en la rama de respaldo.
        assignments = self.service.compute_assignments(
            participants=participants,
            scorer_ids=[me.participant_id, partner.participant_id, rival_one.participant_id],
            creator_participant_id=me.participant_id,
            match_format=MatchFormat.FOURSOMES,
        )

        # Una pareja no se reparte jugador a jugador: los tres llevan lo mismo.
        assert set(assignments[me.participant_id]) == everyone
        assert set(assignments[partner.participant_id]) == everyone
        assert set(assignments[rival_one.participant_id]) == everyone

    def test_fourball_still_splits_player_by_player(self):
        me = _registered_on("A")
        partner = _registered_on("A")
        rival_one = _guest_on("B")
        rival_two = _guest_on("B")

        assignments = self.service.compute_assignments(
            participants=[me, partner, rival_one, rival_two],
            scorer_ids=[me.participant_id, partner.participant_id],
            creator_participant_id=me.participant_id,
            match_format=MatchFormat.FOURBALL,
        )

        # Cada uno juega su bola: el reparto uniforme sigue teniendo sentido y
        # cada anotador se cubre a si mismo.
        assert me.participant_id in assignments[me.participant_id]
        assert partner.participant_id in assignments[partner.participant_id]
        covered = set(assignments[me.participant_id]) | set(assignments[partner.participant_id])
        assert covered == {
            me.participant_id,
            partner.participant_id,
            rival_one.participant_id,
            rival_two.participant_id,
        }
