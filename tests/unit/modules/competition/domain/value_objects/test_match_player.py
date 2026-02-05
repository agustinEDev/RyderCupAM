"""Tests para MatchPlayer value object."""

import pytest

from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


class TestMatchPlayerCreate:
    """Tests para creación de MatchPlayer"""

    def test_create_with_valid_data(self):
        """Crea MatchPlayer con datos válidos."""
        user_id = UserId.generate()

        player = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=12,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6],
        )

        assert player.user_id == user_id
        assert player.playing_handicap == 12
        assert player.tee_category == TeeCategory.AMATEUR_MALE
        assert len(player.strokes_received) == 12

    def test_create_with_zero_handicap(self):
        """Crea MatchPlayer con handicap 0 (scratch)."""
        player = MatchPlayer.create(
            user_id=UserId.generate(),
            playing_handicap=0,
            tee_category=TeeCategory.CHAMPIONSHIP_MALE,
            strokes_received=[],
        )

        assert player.playing_handicap == 0
        assert len(player.strokes_received) == 0

    def test_create_with_negative_handicap_raises(self):
        """Error si handicap es negativo."""
        with pytest.raises(ValueError, match="must be >= 0"):
            MatchPlayer.create(
                user_id=UserId.generate(),
                playing_handicap=-1,
                tee_category=TeeCategory.AMATEUR_MALE,
                strokes_received=[],
            )

    def test_create_with_invalid_hole_number_raises(self):
        """Error si número de hoyo es inválido."""
        with pytest.raises(ValueError, match="Invalid hole number"):
            MatchPlayer.create(
                user_id=UserId.generate(),
                playing_handicap=5,
                tee_category=TeeCategory.AMATEUR_MALE,
                strokes_received=[1, 2, 3, 19],  # 19 es inválido
            )

    def test_create_with_duplicate_holes_raises(self):
        """Error si hay hoyos duplicados."""
        with pytest.raises(ValueError, match="Duplicate hole numbers"):
            MatchPlayer.create(
                user_id=UserId.generate(),
                playing_handicap=5,
                tee_category=TeeCategory.AMATEUR_MALE,
                strokes_received=[1, 2, 3, 3, 5],  # 3 duplicado
            )


class TestMatchPlayerImmutability:
    """Tests para inmutabilidad de MatchPlayer"""

    def test_is_frozen_dataclass(self):
        """MatchPlayer es inmutable (frozen)."""
        player = MatchPlayer.create(
            user_id=UserId.generate(),
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 2, 3],
        )

        with pytest.raises(AttributeError):
            player.playing_handicap = 15


class TestMatchPlayerQueryMethods:
    """Tests para métodos de consulta"""

    def test_receives_stroke_on_hole_true(self):
        """Retorna True si recibe golpe en el hoyo."""
        player = MatchPlayer.create(
            user_id=UserId.generate(),
            playing_handicap=5,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 3, 5, 7, 9],
        )

        assert player.receives_stroke_on_hole(1) is True
        assert player.receives_stroke_on_hole(5) is True
        assert player.receives_stroke_on_hole(9) is True

    def test_receives_stroke_on_hole_false(self):
        """Retorna False si no recibe golpe en el hoyo."""
        player = MatchPlayer.create(
            user_id=UserId.generate(),
            playing_handicap=5,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 3, 5, 7, 9],
        )

        assert player.receives_stroke_on_hole(2) is False
        assert player.receives_stroke_on_hole(18) is False


class TestMatchPlayerEquality:
    """Tests para igualdad (value object)"""

    def test_same_values_are_equal(self):
        """MatchPlayers con mismos valores son iguales."""
        user_id = UserId.generate()

        player1 = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 2, 3],
        )
        player2 = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 2, 3],
        )

        assert player1 == player2

    def test_different_handicap_not_equal(self):
        """MatchPlayers con diferente handicap no son iguales."""
        user_id = UserId.generate()

        player1 = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 2, 3],
        )
        player2 = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=15,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 2, 3],
        )

        assert player1 != player2

    def test_different_tee_not_equal(self):
        """MatchPlayers con diferente tee no son iguales."""
        user_id = UserId.generate()

        player1 = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=10,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[1, 2, 3],
        )
        player2 = MatchPlayer.create(
            user_id=user_id,
            playing_handicap=10,
            tee_category=TeeCategory.SENIOR_MALE,
            strokes_received=[1, 2, 3],
        )

        assert player1 != player2
