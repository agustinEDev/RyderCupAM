"""
Tests unitarios para el Value Object UserDeviceId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Conversión from_string
- Inmutabilidad
- Comparación e igualdad
"""

import uuid

import pytest

from src.modules.user.domain.value_objects.user_device_id import (
    UserDeviceId,
)


class TestUserDeviceIdGeneration:
    """Tests para la generación de UserDeviceId"""

    def test_generate_creates_valid_uuid(self):
        """
        Test: generate() crea UUID válido
        Given: Llamada al método generate()
        When: Se genera un UserDeviceId
        Then: El valor es un UUID válido
        """
        # Act
        device_id = UserDeviceId.generate()

        # Assert
        assert device_id is not None
        assert isinstance(device_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios UserDeviceId
        Then: Todos son diferentes
        """
        # Act
        ids = [UserDeviceId.generate() for _ in range(10)]

        # Assert
        id_values = [str(device_id.value) for device_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestUserDeviceIdValidation:
    """Tests para la validación de UserDeviceId"""

    def test_valid_uuid_string_accepted(self):
        """
        Test: UUID string válido es aceptado
        Given: String con formato UUID válido
        When: Se crea UserDeviceId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = "7c9e6679-7425-40de-944b-e07fc1f90ae7"

        # Act
        device_id = UserDeviceId(valid_uuid)

        # Assert
        assert str(device_id.value) == valid_uuid

    def test_invalid_uuid_string_rejected(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear UserDeviceId con from_string
        Then: Lanza ValueError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            UserDeviceId.from_string(invalid_uuid)

        assert "ID de dispositivo inválido" in str(exc_info.value)

    def test_empty_string_rejected(self):
        """
        Test: String vacío es rechazado
        Given: String vacío
        When: Se intenta crear UserDeviceId con from_string
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            UserDeviceId.from_string("")


class TestUserDeviceIdFromString:
    """Tests para el método from_string"""

    def test_from_string_with_valid_uuid(self):
        """
        Test: from_string acepta UUID válido
        Given: String UUID válido
        When: Se crea UserDeviceId con from_string
        Then: Retorna UserDeviceId correcto
        """
        # Arrange
        uuid_str = "8d0f7789-8536-51ef-b827-f18fd2e01bf8"

        # Act
        device_id = UserDeviceId.from_string(uuid_str)

        # Assert
        assert isinstance(device_id, UserDeviceId)
        assert str(device_id.value) == uuid_str

    def test_from_string_with_invalid_uuid(self):
        """
        Test: from_string rechaza UUID inválido
        Given: String que no es UUID
        When: Se crea UserDeviceId con from_string
        Then: Lanza ValueError
        """
        # Arrange
        invalid_str = "invalid-device-id"

        # Act & Assert
        with pytest.raises(ValueError):
            UserDeviceId.from_string(invalid_str)


class TestUserDeviceIdComparison:
    """Tests para comparación e igualdad"""

    def test_same_uuid_are_equal(self):
        """
        Test: UserDeviceId con mismo UUID son iguales
        Given: Dos UserDeviceId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
        device_id1 = UserDeviceId(uuid_str)
        device_id2 = UserDeviceId(uuid_str)

        # Act & Assert
        assert device_id1 == device_id2
        assert device_id1.value == device_id2.value

    def test_different_uuid_are_not_equal(self):
        """
        Test: UserDeviceId con UUID diferentes no son iguales
        Given: Dos UserDeviceId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        device_id1 = UserDeviceId.generate()
        device_id2 = UserDeviceId.generate()

        # Act & Assert
        assert device_id1 != device_id2


class TestUserDeviceIdStringRepresentation:
    """Tests para representación string"""

    def test_str_returns_value(self):
        """
        Test: __str__ retorna el valor UUID
        Given: UserDeviceId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        device_id = UserDeviceId.generate()

        # Act
        str_representation = str(device_id)

        # Assert
        assert str_representation == str(device_id.value)

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo
        Given: UserDeviceId
        When: Se obtiene __repr__
        Then: Contiene información útil para debugging
        """
        # Arrange
        device_id = UserDeviceId.generate()

        # Act
        repr_str = repr(device_id)

        # Assert
        assert "UserDeviceId" in repr_str
        assert str(device_id.value) in repr_str
