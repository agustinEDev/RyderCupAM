"""Tests para MarkerAssignment Value Object."""

import pytest

from src.modules.competition.domain.value_objects.marker_assignment import (
    MarkerAssignment,
)
from src.modules.user.domain.value_objects.user_id import UserId


class TestMarkerAssignmentCreation:
    """Tests para la creacion de MarkerAssignment."""

    def test_create_valid_assignment(self):
        """Crea un MarkerAssignment valido con 3 jugadores distintos."""
        scorer = UserId.generate()
        marks = UserId.generate()
        marked_by = UserId.generate()
        assignment = MarkerAssignment(
            scorer_user_id=scorer,
            marks_user_id=marks,
            marked_by_user_id=marked_by,
        )
        assert assignment.scorer_user_id == scorer
        assert assignment.marks_user_id == marks
        assert assignment.marked_by_user_id == marked_by

    def test_scorer_cannot_mark_self(self):
        """Un jugador no puede marcarse a si mismo."""
        player = UserId.generate()
        other = UserId.generate()
        with pytest.raises(ValueError, match="no puede marcarse a si mismo"):
            MarkerAssignment(
                scorer_user_id=player,
                marks_user_id=player,
                marked_by_user_id=other,
            )

    def test_scorer_cannot_be_marked_by_self(self):
        """Un jugador no puede ser marcado por si mismo."""
        player = UserId.generate()
        other = UserId.generate()
        with pytest.raises(ValueError, match="no puede ser marcado por si mismo"):
            MarkerAssignment(
                scorer_user_id=player,
                marks_user_id=other,
                marked_by_user_id=player,
            )

    def test_marks_can_equal_marked_by(self):
        """marks_user_id y marked_by_user_id pueden ser el mismo jugador (reciproco en singles)."""
        scorer = UserId.generate()
        opponent = UserId.generate()
        assignment = MarkerAssignment(
            scorer_user_id=scorer,
            marks_user_id=opponent,
            marked_by_user_id=opponent,
        )
        assert assignment.marks_user_id == assignment.marked_by_user_id


class TestMarkerAssignmentImmutability:
    """Tests para inmutabilidad."""

    def test_is_frozen(self):
        """MarkerAssignment es inmutable (frozen dataclass)."""
        scorer = UserId.generate()
        marks = UserId.generate()
        marked_by = UserId.generate()
        assignment = MarkerAssignment(
            scorer_user_id=scorer,
            marks_user_id=marks,
            marked_by_user_id=marked_by,
        )
        with pytest.raises(AttributeError):
            assignment.scorer_user_id = UserId.generate()


class TestMarkerAssignmentEquality:
    """Tests para igualdad."""

    def test_equal_assignments(self):
        """Dos assignments con mismos valores son iguales."""
        scorer = UserId.generate()
        marks = UserId.generate()
        marked_by = UserId.generate()
        a1 = MarkerAssignment(scorer_user_id=scorer, marks_user_id=marks, marked_by_user_id=marked_by)
        a2 = MarkerAssignment(scorer_user_id=scorer, marks_user_id=marks, marked_by_user_id=marked_by)
        assert a1 == a2

    def test_different_assignments(self):
        """Dos assignments con distintos valores no son iguales."""
        a1 = MarkerAssignment(
            scorer_user_id=UserId.generate(),
            marks_user_id=UserId.generate(),
            marked_by_user_id=UserId.generate(),
        )
        a2 = MarkerAssignment(
            scorer_user_id=UserId.generate(),
            marks_user_id=UserId.generate(),
            marked_by_user_id=UserId.generate(),
        )
        assert a1 != a2
