"""Tests para HoleScore Entity."""

import pytest

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.value_objects.hole_score_id import HoleScoreId
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId


@pytest.fixture
def match_id():
    return MatchId.generate()


@pytest.fixture
def player_id():
    return UserId.generate()


def _create_hole_score(match_id, player_id, hole=1, team="A", strokes=0):
    """Helper para crear HoleScore."""
    return HoleScore.create(
        match_id=match_id,
        hole_number=hole,
        player_user_id=player_id,
        team=team,
        strokes_received=strokes,
    )


class TestHoleScoreCreate:
    """Tests para el factory method create."""

    def test_create_default_values(self, match_id, player_id):
        """create() genera HoleScore con valores por defecto correctos."""
        hs = _create_hole_score(match_id, player_id)
        assert hs.match_id == match_id
        assert hs.hole_number == 1
        assert hs.player_user_id == player_id
        assert hs.team == "A"
        assert hs.own_score is None
        assert hs.own_submitted is False
        assert hs.marker_score is None
        assert hs.marker_submitted is False
        assert hs.strokes_received == 0
        assert hs.net_score is None
        assert hs.validation_status == ValidationStatus.PENDING
        assert isinstance(hs.id, HoleScoreId)

    def test_create_hole_1(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id, hole=1)
        assert hs.hole_number == 1

    def test_create_hole_18(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id, hole=18)
        assert hs.hole_number == 18

    def test_create_hole_0_raises(self, match_id, player_id):
        with pytest.raises(ValueError, match="hole_number must be between"):
            _create_hole_score(match_id, player_id, hole=0)

    def test_create_hole_19_raises(self, match_id, player_id):
        with pytest.raises(ValueError, match="hole_number must be between"):
            _create_hole_score(match_id, player_id, hole=19)

    def test_create_team_a(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id, team="A")
        assert hs.team == "A"

    def test_create_team_b(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id, team="B")
        assert hs.team == "B"

    def test_create_invalid_team_raises(self, match_id, player_id):
        with pytest.raises(ValueError, match="team must be"):
            _create_hole_score(match_id, player_id, team="C")

    def test_create_strokes_0(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id, strokes=0)
        assert hs.strokes_received == 0

    def test_create_strokes_1(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id, strokes=1)
        assert hs.strokes_received == 1

    def test_create_strokes_2(self, match_id, player_id):
        """PH > 18: un hoyo puede recibir 2+ strokes."""
        hs = _create_hole_score(match_id, player_id, strokes=2)
        assert hs.strokes_received == 2

    def test_create_invalid_strokes_raises(self, match_id, player_id):
        with pytest.raises(ValueError, match="strokes_received must be"):
            _create_hole_score(match_id, player_id, strokes=-1)


class TestHoleScoreSetOwnScore:
    """Tests para set_own_score."""

    def test_set_own_score_valid(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(5)
        assert hs.own_score == 5
        assert hs.own_submitted is True

    def test_set_own_score_min(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(1)
        assert hs.own_score == 1

    def test_set_own_score_max(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(9)
        assert hs.own_score == 9

    def test_set_own_score_none_picked_up(self, match_id, player_id):
        """None = picked up ball."""
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(None)
        assert hs.own_score is None
        assert hs.own_submitted is True

    def test_set_own_score_0_raises(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        with pytest.raises(ValueError, match="Score must be between"):
            hs.set_own_score(0)

    def test_set_own_score_10_raises(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        with pytest.raises(ValueError, match="Score must be between"):
            hs.set_own_score(10)

    def test_set_own_score_overwrites(self, match_id, player_id):
        """Puede sobrescribir score existente."""
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(5)
        hs.set_own_score(4)
        assert hs.own_score == 4


class TestHoleScoreSetMarkerScore:
    """Tests para set_marker_score."""

    def test_set_marker_score_valid(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_marker_score(5)
        assert hs.marker_score == 5
        assert hs.marker_submitted is True

    def test_set_marker_score_none_picked_up(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_marker_score(None)
        assert hs.marker_score is None
        assert hs.marker_submitted is True

    def test_set_marker_score_0_raises(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        with pytest.raises(ValueError, match="Score must be between"):
            hs.set_marker_score(0)

    def test_set_marker_score_10_raises(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        with pytest.raises(ValueError, match="Score must be between"):
            hs.set_marker_score(10)


class TestHoleScoreValidation:
    """Tests para recalculate_validation."""

    def test_pending_when_neither_submitted(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.PENDING

    def test_pending_when_only_own_submitted(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(5)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.PENDING

    def test_pending_when_only_marker_submitted(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_marker_score(5)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.PENDING

    def test_match_when_scores_equal(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(5)
        hs.set_marker_score(5)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.MATCH

    def test_match_when_both_none(self, match_id, player_id):
        """None == None → MATCH (ambos picked up)."""
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(None)
        hs.set_marker_score(None)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.MATCH

    def test_mismatch_when_scores_differ(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(5)
        hs.set_marker_score(4)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.MISMATCH

    def test_mismatch_when_null_vs_number(self, match_id, player_id):
        """None vs numero → MISMATCH."""
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(None)
        hs.set_marker_score(5)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.MISMATCH

    def test_mismatch_when_number_vs_null(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        hs.set_own_score(5)
        hs.set_marker_score(None)
        hs.recalculate_validation()
        assert hs.validation_status == ValidationStatus.MISMATCH


class TestHoleScoreNetScore:
    """Tests para calculo de net score."""

    def test_net_score_without_stroke(self, match_id, player_id):
        """Net = own_score cuando strokes_received=0."""
        hs = _create_hole_score(match_id, player_id, strokes=0)
        hs.set_own_score(5)
        hs.set_marker_score(5)
        hs.recalculate_validation()
        assert hs.net_score == 5

    def test_net_score_with_stroke(self, match_id, player_id):
        """Net = own_score - 1 cuando strokes_received=1."""
        hs = _create_hole_score(match_id, player_id, strokes=1)
        hs.set_own_score(5)
        hs.set_marker_score(5)
        hs.recalculate_validation()
        assert hs.net_score == 4

    def test_net_score_min_zero(self, match_id, player_id):
        """Net score no puede ser negativo (min 0)."""
        hs = _create_hole_score(match_id, player_id, strokes=1)
        hs.set_own_score(1)
        hs.set_marker_score(1)
        hs.recalculate_validation()
        assert hs.net_score == 0

    def test_net_score_none_when_picked_up(self, match_id, player_id):
        """Net = None cuando picked up (own_score=None)."""
        hs = _create_hole_score(match_id, player_id, strokes=0)
        hs.set_own_score(None)
        hs.set_marker_score(None)
        hs.recalculate_validation()
        assert hs.net_score is None

    def test_net_score_none_when_mismatch(self, match_id, player_id):
        """Net = None cuando MISMATCH."""
        hs = _create_hole_score(match_id, player_id, strokes=0)
        hs.set_own_score(5)
        hs.set_marker_score(4)
        hs.recalculate_validation()
        assert hs.net_score is None

    def test_net_score_none_when_pending(self, match_id, player_id):
        """Net = None cuando PENDING."""
        hs = _create_hole_score(match_id, player_id, strokes=0)
        hs.set_own_score(5)
        hs.recalculate_validation()
        assert hs.net_score is None


class TestHoleScoreReconstruct:
    """Tests para reconstruct."""

    def test_reconstruct_preserves_all_fields(self, match_id, player_id):
        hs_id = HoleScoreId.generate()
        from datetime import datetime

        now = datetime.now()
        hs = HoleScore.reconstruct(
            id=hs_id,
            match_id=match_id,
            hole_number=5,
            player_user_id=player_id,
            team="B",
            own_score=4,
            own_submitted=True,
            marker_score=4,
            marker_submitted=True,
            strokes_received=1,
            net_score=3,
            validation_status=ValidationStatus.MATCH,
            created_at=now,
            updated_at=now,
        )
        assert hs.id == hs_id
        assert hs.hole_number == 5
        assert hs.team == "B"
        assert hs.own_score == 4
        assert hs.own_submitted is True
        assert hs.marker_score == 4
        assert hs.marker_submitted is True
        assert hs.strokes_received == 1
        assert hs.net_score == 3
        assert hs.validation_status == ValidationStatus.MATCH


class TestHoleScoreEquality:
    """Tests para igualdad."""

    def test_equal_by_id(self, match_id, player_id):
        hs1 = _create_hole_score(match_id, player_id)
        hs2 = HoleScore.reconstruct(
            id=hs1.id,
            match_id=match_id,
            hole_number=1,
            player_user_id=player_id,
            team="A",
            own_score=None,
            own_submitted=False,
            marker_score=None,
            marker_submitted=False,
            strokes_received=0,
            net_score=None,
            validation_status=ValidationStatus.PENDING,
            created_at=hs1.created_at,
            updated_at=hs1.updated_at,
        )
        assert hs1 == hs2

    def test_not_equal_to_other_type(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        assert hs != "not-a-holescore"

    def test_hash_by_id(self, match_id, player_id):
        hs = _create_hole_score(match_id, player_id)
        assert hash(hs) == hash(hs.id)
