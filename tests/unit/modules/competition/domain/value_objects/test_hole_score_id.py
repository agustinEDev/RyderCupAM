"""Tests para HoleScoreId Value Object."""

import uuid

import pytest

from src.modules.competition.domain.value_objects.hole_score_id import (
    HoleScoreId,
    InvalidHoleScoreIdError,
)


class TestHoleScoreIdCreation:
    """Tests para la creacion de HoleScoreId."""

    def test_create_from_uuid(self):
        """Crea HoleScoreId desde un objeto UUID."""
        uid = uuid.uuid4()
        hole_score_id = HoleScoreId(uid)
        assert hole_score_id.value == uid

    def test_create_from_string(self):
        """Crea HoleScoreId desde un string UUID valido."""
        uid = uuid.uuid4()
        hole_score_id = HoleScoreId(str(uid))
        assert hole_score_id.value == uid

    def test_create_from_invalid_string_raises(self):
        """String no-UUID lanza InvalidHoleScoreIdError."""
        with pytest.raises(InvalidHoleScoreIdError):
            HoleScoreId("not-a-uuid")

    def test_create_from_empty_string_raises(self):
        """String vacio lanza InvalidHoleScoreIdError."""
        with pytest.raises(InvalidHoleScoreIdError):
            HoleScoreId("")

    def test_create_from_int_raises(self):
        """Tipo no soportado lanza InvalidHoleScoreIdError."""
        with pytest.raises(InvalidHoleScoreIdError):
            HoleScoreId(123)

    def test_create_from_none_raises(self):
        """None lanza InvalidHoleScoreIdError."""
        with pytest.raises(InvalidHoleScoreIdError):
            HoleScoreId(None)


class TestHoleScoreIdGenerate:
    """Tests para el factory method generate."""

    def test_generate_creates_valid_id(self):
        """generate() crea un HoleScoreId valido."""
        hole_score_id = HoleScoreId.generate()
        assert isinstance(hole_score_id, HoleScoreId)
        assert isinstance(hole_score_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """generate() crea IDs unicos."""
        id1 = HoleScoreId.generate()
        id2 = HoleScoreId.generate()
        assert id1 != id2


class TestHoleScoreIdEquality:
    """Tests para igualdad y hash."""

    def test_same_uuid_are_equal(self):
        """Dos HoleScoreId con el mismo UUID son iguales."""
        uid = uuid.uuid4()
        id1 = HoleScoreId(uid)
        id2 = HoleScoreId(uid)
        assert id1 == id2

    def test_different_uuid_are_not_equal(self):
        """Dos HoleScoreId con distinto UUID no son iguales."""
        id1 = HoleScoreId.generate()
        id2 = HoleScoreId.generate()
        assert id1 != id2

    def test_not_equal_to_other_type(self):
        """HoleScoreId no es igual a otro tipo."""
        hole_score_id = HoleScoreId.generate()
        assert hole_score_id != "some-string"

    def test_hash_consistency(self):
        """IDs iguales tienen el mismo hash."""
        uid = uuid.uuid4()
        id1 = HoleScoreId(uid)
        id2 = HoleScoreId(uid)
        assert hash(id1) == hash(id2)

    def test_usable_in_set(self):
        """HoleScoreId puede usarse en sets."""
        uid = uuid.uuid4()
        id1 = HoleScoreId(uid)
        id2 = HoleScoreId(uid)
        assert len({id1, id2}) == 1


class TestHoleScoreIdStr:
    """Tests para representacion string."""

    def test_str_returns_uuid_string(self):
        """str() retorna el UUID como string."""
        uid = uuid.uuid4()
        hole_score_id = HoleScoreId(uid)
        assert str(hole_score_id) == str(uid)


class TestHoleScoreIdOrdering:
    """Tests para comparacion."""

    def test_lt_comparison(self):
        """HoleScoreId soporta comparacion menor-que."""
        id1 = HoleScoreId(uuid.UUID("00000000-0000-0000-0000-000000000001"))
        id2 = HoleScoreId(uuid.UUID("00000000-0000-0000-0000-000000000002"))
        assert id1 < id2

    def test_lt_with_non_hole_score_id(self):
        """Comparar con otro tipo retorna NotImplemented."""
        hole_score_id = HoleScoreId.generate()
        assert hole_score_id.__lt__("string") is NotImplemented


class TestHoleScoreIdFrozen:
    """Tests para inmutabilidad."""

    def test_is_frozen(self):
        """HoleScoreId es inmutable (frozen dataclass)."""
        hole_score_id = HoleScoreId.generate()
        with pytest.raises(AttributeError):
            hole_score_id.value = uuid.uuid4()
