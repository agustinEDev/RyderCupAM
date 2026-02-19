"""Tests para InvitationId Value Object."""

import uuid

import pytest

from src.modules.competition.domain.value_objects.invitation_id import (
    InvalidInvitationIdError,
    InvitationId,
)


class TestInvitationIdCreation:
    """Tests para la creacion de InvitationId."""

    def test_create_from_uuid(self):
        """Crea InvitationId desde un objeto UUID."""
        uid = uuid.uuid4()
        invitation_id = InvitationId(uid)
        assert invitation_id.value == uid

    def test_create_from_string(self):
        """Crea InvitationId desde un string UUID valido."""
        uid = uuid.uuid4()
        invitation_id = InvitationId(str(uid))
        assert invitation_id.value == uid

    def test_create_from_invalid_string_raises(self):
        """String no-UUID lanza InvalidInvitationIdError."""
        with pytest.raises(InvalidInvitationIdError):
            InvitationId("not-a-uuid")

    def test_create_from_empty_string_raises(self):
        """String vacio lanza InvalidInvitationIdError."""
        with pytest.raises(InvalidInvitationIdError):
            InvitationId("")

    def test_create_from_int_raises(self):
        """Tipo no soportado lanza InvalidInvitationIdError."""
        with pytest.raises(InvalidInvitationIdError):
            InvitationId(123)

    def test_create_from_none_raises(self):
        """None lanza InvalidInvitationIdError."""
        with pytest.raises(InvalidInvitationIdError):
            InvitationId(None)


class TestInvitationIdGenerate:
    """Tests para el factory method generate."""

    def test_generate_creates_valid_id(self):
        """generate() crea un InvitationId valido."""
        invitation_id = InvitationId.generate()
        assert isinstance(invitation_id, InvitationId)
        assert isinstance(invitation_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """generate() crea IDs unicos."""
        id1 = InvitationId.generate()
        id2 = InvitationId.generate()
        assert id1 != id2


class TestInvitationIdEquality:
    """Tests para igualdad y hash."""

    def test_same_uuid_are_equal(self):
        """Dos InvitationId con el mismo UUID son iguales."""
        uid = uuid.uuid4()
        id1 = InvitationId(uid)
        id2 = InvitationId(uid)
        assert id1 == id2

    def test_different_uuid_are_not_equal(self):
        """Dos InvitationId con distinto UUID no son iguales."""
        id1 = InvitationId.generate()
        id2 = InvitationId.generate()
        assert id1 != id2

    def test_not_equal_to_other_type(self):
        """InvitationId no es igual a otro tipo."""
        invitation_id = InvitationId.generate()
        assert invitation_id != "some-string"

    def test_hash_consistency(self):
        """IDs iguales tienen el mismo hash."""
        uid = uuid.uuid4()
        id1 = InvitationId(uid)
        id2 = InvitationId(uid)
        assert hash(id1) == hash(id2)

    def test_usable_in_set(self):
        """InvitationId puede usarse en sets."""
        uid = uuid.uuid4()
        id1 = InvitationId(uid)
        id2 = InvitationId(uid)
        assert len({id1, id2}) == 1


class TestInvitationIdStr:
    """Tests para representacion string."""

    def test_str_returns_uuid_string(self):
        """str() retorna el UUID como string."""
        uid = uuid.uuid4()
        invitation_id = InvitationId(uid)
        assert str(invitation_id) == str(uid)


class TestInvitationIdOrdering:
    """Tests para comparacion."""

    def test_lt_comparison(self):
        """InvitationId soporta comparacion menor-que."""
        id1 = InvitationId(uuid.UUID("00000000-0000-0000-0000-000000000001"))
        id2 = InvitationId(uuid.UUID("00000000-0000-0000-0000-000000000002"))
        assert id1 < id2

    def test_lt_with_non_invitation_id(self):
        """Comparar con otro tipo retorna NotImplemented."""
        invitation_id = InvitationId.generate()
        assert invitation_id.__lt__("string") is NotImplemented


class TestInvitationIdFrozen:
    """Tests para inmutabilidad."""

    def test_is_frozen(self):
        """InvitationId es inmutable (frozen dataclass)."""
        invitation_id = InvitationId.generate()
        with pytest.raises(AttributeError):
            invitation_id.value = uuid.uuid4()
