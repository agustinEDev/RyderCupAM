# -*- coding: utf-8 -*-
"""
Tests unitarios para el Value Object UserId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Inmutabilidad
- Comparación e igualdad
"""

import pytest
import uuid

from src.modules.user.domain.value_objects.user_id import UserId, InvalidUserIdError


class TestUserIdGeneration:
    """Tests para la generación de UserId"""

    def test_generate_creates_valid_uuid(self):
        """
        Test: generate() crea UUID válido
        Given: Llamada al método generate()
        When: Se genera un UserId
        Then: El valor es un UUID válido
        """
        # Act
        user_id = UserId.generate()
        
        # Assert
        assert user_id is not None
        assert isinstance(user_id.value, str)
        # Verifica que es UUID válido intentando parsearlo
        uuid_obj = uuid.UUID(user_id.value)
        assert str(uuid_obj) == user_id.value

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios UserId
        Then: Todos son diferentes
        """
        # Act
        ids = [UserId.generate() for _ in range(10)]
        
        # Assert
        id_values = [user_id.value for user_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestUserIdValidation:
    """Tests para la validación de UserId"""

    def test_valid_uuid_string_accepted(self):
        """
        Test: UUID string válido es aceptado
        Given: String con formato UUID válido
        When: Se crea UserId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        
        # Act
        user_id = UserId(valid_uuid)
        
        # Assert
        assert user_id.value == valid_uuid

    def test_invalid_uuid_string_rejected(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear UserId
        Then: Lanza InvalidUserIdError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"
        
        # Act & Assert
        with pytest.raises(InvalidUserIdError) as exc_info:
            UserId(invalid_uuid)
        
        assert "no es un UUID válido" in str(exc_info.value)

    def test_empty_string_rejected(self):
        """
        Test: String vacío es rechazado
        Given: String vacío
        When: Se intenta crear UserId
        Then: Lanza InvalidUserIdError
        """
        # Act & Assert
        with pytest.raises(InvalidUserIdError):
            UserId("")

    def test_none_value_rejected(self):
        """
        Test: Valor None es rechazado
        Given: Valor None
        When: Se intenta crear UserId
        Then: Lanza error (TypeError o InvalidUserIdError)
        """
        # Act & Assert
        with pytest.raises((InvalidUserIdError, TypeError)):
            UserId(None)


class TestUserIdComparison:
    """Tests para comparación e igualdad"""

    def test_same_uuid_are_equal(self):
        """
        Test: UserId con mismo UUID son iguales
        Given: Dos UserId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        user_id1 = UserId(uuid_str)
        user_id2 = UserId(uuid_str)
        
        # Act & Assert
        assert user_id1 == user_id2
        assert user_id1.value == user_id2.value

    def test_different_uuid_are_not_equal(self):
        """
        Test: UserId con UUID diferentes no son iguales
        Given: Dos UserId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        user_id1 = UserId.generate()
        user_id2 = UserId.generate()
        
        # Act & Assert
        assert user_id1 != user_id2

    def test_comparison_with_non_userid_is_false(self):
        """
        Test: Comparación con objeto que no es UserId es False
        Given: UserId y string
        When: Se comparan
        Then: No son iguales
        """
        # Arrange
        user_id = UserId.generate()
        
        # Act & Assert
        assert user_id != "some-string"
        assert user_id != 123
        assert user_id != None


class TestUserIdImmutability:
    """Tests para inmutabilidad"""

    def test_userid_is_immutable(self):
        """
        Test: UserId es inmutable
        Given: UserId creado
        When: Se intenta modificar el valor
        Then: Lanza error de atributo
        """
        # Arrange
        user_id = UserId.generate()
        original_value = user_id.value
        
        # Act & Assert
        with pytest.raises(AttributeError):
            user_id.value = "new-value"
        
        # Verificar que el valor no cambió
        assert user_id.value == original_value


class TestUserIdStringRepresentation:
    """Tests para representación string"""

    def test_str_returns_value(self):
        """
        Test: __str__ retorna el valor UUID
        Given: UserId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        user_id = UserId.generate()
        
        # Act
        str_representation = str(user_id)
        
        # Assert
        assert str_representation == user_id.value

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo
        Given: UserId
        When: Se obtiene __repr__
        Then: Contiene información útil para debugging
        """
        # Arrange
        user_id = UserId.generate()
        
        # Act
        repr_str = repr(user_id)
        
        # Assert
        assert "UserId" in repr_str
        assert user_id.value in repr_str
