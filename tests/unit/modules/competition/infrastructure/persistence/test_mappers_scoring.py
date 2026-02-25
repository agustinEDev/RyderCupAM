"""Tests para TypeDecorators y JSONB serialization del Scoring Module (Block 6)."""

import uuid

from src.modules.competition.domain.value_objects.hole_score_id import HoleScoreId
from src.modules.competition.domain.value_objects.marker_assignment import (
    MarkerAssignment,
)
from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    HoleScoreIdDecorator,
    MarkerAssignmentsJsonType,
    ScorecardSubmittedByJsonType,
    _create_enum_decorator,
)
from src.modules.user.domain.value_objects.user_id import UserId

# ==================== HoleScoreIdDecorator ====================


class TestHoleScoreIdDecorator:
    """Tests para HoleScoreIdDecorator TypeDecorator."""

    def setup_method(self):
        self.decorator = HoleScoreIdDecorator()

    def test_process_bind_param_with_hole_score_id(self):
        """Serializa HoleScoreId a string UUID."""
        hs_id = HoleScoreId.generate()
        result = self.decorator.process_bind_param(hs_id, None)
        assert result == str(hs_id.value)

    def test_process_bind_param_with_string(self):
        """Acepta string directamente."""
        uid = str(uuid.uuid4())
        result = self.decorator.process_bind_param(uid, None)
        assert result == uid

    def test_process_bind_param_with_none(self):
        """Retorna None para None."""
        assert self.decorator.process_bind_param(None, None) is None

    def test_process_result_value_to_hole_score_id(self):
        """Deserializa string a HoleScoreId."""
        uid = str(uuid.uuid4())
        result = self.decorator.process_result_value(uid, None)
        assert isinstance(result, HoleScoreId)
        assert str(result.value) == uid

    def test_process_result_value_none(self):
        """Retorna None para None."""
        assert self.decorator.process_result_value(None, None) is None

    def test_roundtrip(self):
        """Serializa y deserializa HoleScoreId correctamente."""
        hs_id = HoleScoreId.generate()
        serialized = self.decorator.process_bind_param(hs_id, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert isinstance(deserialized, HoleScoreId)
        assert deserialized == hs_id


# ==================== ValidationStatusDecorator ====================


class TestValidationStatusDecorator:
    """Tests para ValidationStatusDecorator via _create_enum_decorator."""

    def setup_method(self):
        decorator_cls = _create_enum_decorator(ValidationStatus)
        self.decorator = decorator_cls()

    def test_bind_pending(self):
        """Serializa PENDING a string."""
        result = self.decorator.process_bind_param(ValidationStatus.PENDING, None)
        assert result == "PENDING"

    def test_bind_match(self):
        """Serializa MATCH a string."""
        result = self.decorator.process_bind_param(ValidationStatus.MATCH, None)
        assert result == "MATCH"

    def test_bind_mismatch(self):
        """Serializa MISMATCH a string."""
        result = self.decorator.process_bind_param(ValidationStatus.MISMATCH, None)
        assert result == "MISMATCH"

    def test_bind_none(self):
        """Retorna None para None."""
        assert self.decorator.process_bind_param(None, None) is None

    def test_result_pending(self):
        """Deserializa string a ValidationStatus.PENDING."""
        result = self.decorator.process_result_value("PENDING", None)
        assert result == ValidationStatus.PENDING

    def test_result_match(self):
        """Deserializa string a ValidationStatus.MATCH."""
        result = self.decorator.process_result_value("MATCH", None)
        assert result == ValidationStatus.MATCH

    def test_result_mismatch(self):
        """Deserializa string a ValidationStatus.MISMATCH."""
        result = self.decorator.process_result_value("MISMATCH", None)
        assert result == ValidationStatus.MISMATCH

    def test_result_none(self):
        """Retorna None para None."""
        assert self.decorator.process_result_value(None, None) is None

    def test_roundtrip(self):
        """Serializa y deserializa cada status correctamente."""
        for status in ValidationStatus:
            serialized = self.decorator.process_bind_param(status, None)
            deserialized = self.decorator.process_result_value(serialized, None)
            assert deserialized == status


# ==================== MarkerAssignmentsJsonType ====================


class TestMarkerAssignmentsJsonType:
    """Tests para MarkerAssignmentsJsonType JSONB TypeDecorator."""

    def setup_method(self):
        self.decorator = MarkerAssignmentsJsonType()

    def test_bind_empty_tuple(self):
        """Tupla vacia se serializa a None."""
        result = self.decorator.process_bind_param((), None)
        assert result is None

    def test_bind_none(self):
        """None se serializa a None."""
        result = self.decorator.process_bind_param(None, None)
        assert result is None

    def test_bind_single_assignment(self):
        """Serializa una MarkerAssignment a lista de dicts."""
        a, b = UserId.generate(), UserId.generate()
        ma = MarkerAssignment(scorer_user_id=a, marks_user_id=b, marked_by_user_id=b)
        result = self.decorator.process_bind_param((ma,), None)
        assert len(result) == 1
        assert result[0]["scorer_user_id"] == str(a.value)
        assert result[0]["marks_user_id"] == str(b.value)
        assert result[0]["marked_by_user_id"] == str(b.value)

    def test_bind_multiple_assignments(self):
        """Serializa multiples MarkerAssignment."""
        a, b = UserId.generate(), UserId.generate()
        ma1 = MarkerAssignment(scorer_user_id=a, marks_user_id=b, marked_by_user_id=b)
        ma2 = MarkerAssignment(scorer_user_id=b, marks_user_id=a, marked_by_user_id=a)
        result = self.decorator.process_bind_param((ma1, ma2), None)
        assert len(result) == 2

    def test_result_none(self):
        """NULL en BD retorna tupla vacia."""
        result = self.decorator.process_result_value(None, None)
        assert result == ()

    def test_result_empty_list(self):
        """Lista vacia retorna tupla vacia."""
        result = self.decorator.process_result_value([], None)
        assert result == ()

    def test_result_single_assignment(self):
        """Deserializa un dict a MarkerAssignment."""
        a_str, b_str = str(uuid.uuid4()), str(uuid.uuid4())
        data = [{"scorer_user_id": a_str, "marks_user_id": b_str, "marked_by_user_id": b_str}]
        result = self.decorator.process_result_value(data, None)
        assert len(result) == 1
        assert isinstance(result[0], MarkerAssignment)
        assert str(result[0].scorer_user_id.value) == a_str

    def test_roundtrip(self):
        """Serializa y deserializa sin perdida de datos."""
        a, b = UserId.generate(), UserId.generate()
        ma = MarkerAssignment(scorer_user_id=a, marks_user_id=b, marked_by_user_id=b)
        original = (ma,)
        serialized = self.decorator.process_bind_param(original, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert len(deserialized) == 1
        assert deserialized[0].scorer_user_id == a
        assert deserialized[0].marks_user_id == b
        assert deserialized[0].marked_by_user_id == b


# ==================== ScorecardSubmittedByJsonType ====================


class TestScorecardSubmittedByJsonType:
    """Tests para ScorecardSubmittedByJsonType JSONB TypeDecorator."""

    def setup_method(self):
        self.decorator = ScorecardSubmittedByJsonType()

    def test_bind_empty_tuple(self):
        """Tupla vacia se serializa a None."""
        result = self.decorator.process_bind_param((), None)
        assert result is None

    def test_bind_none(self):
        """None se serializa a None."""
        result = self.decorator.process_bind_param(None, None)
        assert result is None

    def test_bind_user_ids(self):
        """Serializa UserIds a lista de strings."""
        a, b = UserId.generate(), UserId.generate()
        result = self.decorator.process_bind_param((a, b), None)
        assert len(result) == 2
        assert result[0] == str(a.value)
        assert result[1] == str(b.value)

    def test_result_none(self):
        """NULL en BD retorna tupla vacia."""
        result = self.decorator.process_result_value(None, None)
        assert result == ()

    def test_result_empty_list(self):
        """Lista vacia retorna tupla vacia."""
        result = self.decorator.process_result_value([], None)
        assert result == ()

    def test_result_user_ids(self):
        """Deserializa strings a UserId."""
        uid_str = str(uuid.uuid4())
        result = self.decorator.process_result_value([uid_str], None)
        assert len(result) == 1
        assert isinstance(result[0], UserId)
        assert str(result[0].value) == uid_str

    def test_roundtrip(self):
        """Serializa y deserializa sin perdida de datos."""
        a, b = UserId.generate(), UserId.generate()
        original = (a, b)
        serialized = self.decorator.process_bind_param(original, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert len(deserialized) == 2
        assert deserialized[0] == a
        assert deserialized[1] == b
