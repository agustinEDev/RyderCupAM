"""
Tests unitarios para el Value Object OAuthAccountId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Comparación e igualdad
- Representación string
"""

import uuid

import pytest

from src.modules.user.domain.value_objects.oauth_account_id import OAuthAccountId


class TestOAuthAccountIdGeneration:
    """Tests para la generación de OAuthAccountId"""

    def test_create_with_uuid(self):
        """
        Test: Creación con UUID object válido
        Given: Un UUID válido
        When: Se crea OAuthAccountId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = uuid.uuid4()

        # Act
        account_id = OAuthAccountId(valid_uuid)

        # Assert
        assert account_id.value == valid_uuid

    def test_create_with_string(self):
        """
        Test: Creación con string UUID válido
        Given: String con formato UUID válido
        When: Se crea OAuthAccountId
        Then: Se acepta y convierte a UUID
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        account_id = OAuthAccountId(uuid_str)

        # Assert
        assert str(account_id.value) == uuid_str

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios OAuthAccountId
        Then: Todos son diferentes
        """
        # Act
        ids = [OAuthAccountId.generate() for _ in range(10)]

        # Assert
        id_values = [str(account_id.value) for account_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestOAuthAccountIdComparison:
    """Tests para comparación e igualdad"""

    def test_equality_same_value(self):
        """
        Test: OAuthAccountId con mismo UUID son iguales
        Given: Dos OAuthAccountId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        account_id1 = OAuthAccountId(uuid_str)
        account_id2 = OAuthAccountId(uuid_str)

        # Act & Assert
        assert account_id1 == account_id2
        assert account_id1.value == account_id2.value

    def test_equality_different_value(self):
        """
        Test: OAuthAccountId con UUID diferentes no son iguales
        Given: Dos OAuthAccountId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        account_id1 = OAuthAccountId.generate()
        account_id2 = OAuthAccountId.generate()

        # Act & Assert
        assert account_id1 != account_id2

    def test_hash_consistency(self):
        """
        Test: __hash__ permite usar OAuthAccountId en sets y dicts
        Given: Varios OAuthAccountId
        When: Se usan como claves de dict o en set
        Then: Funcionan correctamente
        """
        # Arrange
        id1 = OAuthAccountId.generate()
        id2 = OAuthAccountId.generate()
        id3 = OAuthAccountId(str(id1.value))  # Mismo UUID que id1

        # Act
        id_set = {id1, id2, id3}
        id_dict = {id1: "value1", id2: "value2"}

        # Assert
        assert len(id_set) == 2  # id1 y id3 son el mismo
        assert id_dict[id1] == "value1"
        assert id_dict[id3] == "value1"  # Accede con el mismo valor


class TestOAuthAccountIdValidation:
    """Tests para validación de OAuthAccountId"""

    def test_invalid_string_raises(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear OAuthAccountId
        Then: Lanza ValueError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            OAuthAccountId(invalid_uuid)

        assert "Invalid UUID format" in str(exc_info.value)

    def test_invalid_type_raises(self):
        """
        Test: Tipo inválido es rechazado
        Given: Valor que no es UUID ni string
        When: Se intenta crear OAuthAccountId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            OAuthAccountId(123)

        assert "must be UUID or string" in str(exc_info.value)


class TestOAuthAccountIdStringRepresentation:
    """Tests para representación string"""

    def test_str_representation(self):
        """
        Test: __str__ retorna el UUID como string
        Given: OAuthAccountId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        account_id = OAuthAccountId.generate()

        # Act
        str_representation = str(account_id)

        # Assert
        assert str_representation == str(account_id.value)

    def test_repr_representation(self):
        """
        Test: __repr__ es informativo para debugging
        Given: OAuthAccountId
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        account_id = OAuthAccountId.generate()

        # Act
        repr_str = repr(account_id)

        # Assert
        assert "OAuthAccountId" in repr_str
        assert str(account_id.value) in repr_str
