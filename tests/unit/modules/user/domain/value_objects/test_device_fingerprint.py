"""
Tests unitarios para el Value Object DeviceFingerprint.

Este archivo contiene tests que verifican:
- Creación con user_agent e ip_address (device_name auto-generado)
- Generación automática de hash SHA256
- Parsing de User-Agent para generar device_name
- Normalización de IPv6
- Validación de campos (no vacíos)
- Inmutabilidad y comparación por valor
"""

import hashlib

import pytest

from src.modules.user.domain.value_objects.device_fingerprint import (
    DeviceFingerprint,
)


class TestDeviceFingerprintCreation:
    """Tests para la creación de DeviceFingerprint"""

    def test_create_with_valid_data(self):
        """
        Test: create() con datos válidos
        Given: user_agent, ip_address válidos
        When: Se crea DeviceFingerprint
        Then: Se crea correctamente con device_name auto-generado y hash
        """
        # Arrange
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"
        ip_address = "192.168.1.100"

        # Act
        fingerprint = DeviceFingerprint.create(user_agent, ip_address)

        # Assert
        assert fingerprint.user_agent == user_agent
        assert fingerprint.ip_address == ip_address
        assert fingerprint.device_name == "Chrome on macOS"  # Auto-generado
        assert fingerprint.fingerprint_hash is not None
        assert len(fingerprint.fingerprint_hash) == 64  # SHA256 = 64 caracteres hex

    def test_hash_is_deterministic(self):
        """
        Test: Hash es determinístico (mismo input → mismo hash)
        Given: Dos DeviceFingerprint con datos idénticos
        When: Se generan los hashes
        Then: Ambos hashes son iguales
        """
        # Arrange
        user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
        ip_address = "192.168.1.101"

        # Act
        fingerprint1 = DeviceFingerprint.create(user_agent, ip_address)
        fingerprint2 = DeviceFingerprint.create(user_agent, ip_address)

        # Assert
        assert fingerprint1.fingerprint_hash == fingerprint2.fingerprint_hash
        assert fingerprint1.device_name == "Safari on iOS"

    def test_hash_changes_with_different_data(self):
        """
        Test: Hash cambia con datos diferentes
        Given: Dos DeviceFingerprint con datos distintos
        When: Se generan los hashes
        Then: Los hashes son diferentes
        """
        # Arrange
        fingerprint1 = DeviceFingerprint.create(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
            "192.168.1.100"
        )
        fingerprint2 = DeviceFingerprint.create(
            "Mozilla/5.0 (iPhone) Safari/604.1",
            "192.168.1.101"
        )

        # Act & Assert
        assert fingerprint1.fingerprint_hash != fingerprint2.fingerprint_hash

    def test_hash_formula_uses_user_agent_and_ip(self):
        """
        Test: Hash se genera usando user_agent + "|" + ip_address
        Given: DeviceFingerprint con valores conocidos
        When: Se genera el hash
        Then: El hash coincide con SHA256(user_agent|ip)
        """
        # Arrange
        user_agent = "TestAgent"
        ip_address = "127.0.0.1"

        expected_hash = hashlib.sha256(
            f"{user_agent}|{ip_address}".encode()
        ).hexdigest()

        # Act
        fingerprint = DeviceFingerprint.create(user_agent, ip_address)

        # Assert
        assert fingerprint.fingerprint_hash == expected_hash

    def test_device_name_auto_generated_chrome(self):
        """
        Test: device_name se auto-genera desde User-Agent (Chrome)
        Given: User-Agent de Chrome en macOS
        When: Se crea DeviceFingerprint
        Then: device_name es "Chrome on macOS"
        """
        # Act
        fingerprint = DeviceFingerprint.create(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0",
            "192.168.1.1"
        )

        # Assert
        assert fingerprint.device_name == "Chrome on macOS"

    def test_device_name_auto_generated_firefox(self):
        """
        Test: device_name se auto-genera desde User-Agent (Firefox)
        Given: User-Agent de Firefox en Windows
        When: Se crea DeviceFingerprint
        Then: device_name es "Firefox on Windows 10/11"
        """
        # Act
        fingerprint = DeviceFingerprint.create(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
            "192.168.1.2"
        )

        # Assert
        assert fingerprint.device_name == "Firefox on Windows 10/11"

    def test_device_name_auto_generated_safari_ios(self):
        """
        Test: device_name se auto-genera desde User-Agent (Safari iOS)
        Given: User-Agent de Safari en iPhone
        When: Se crea DeviceFingerprint
        Then: device_name es "Safari on iOS"
        """
        # Act
        fingerprint = DeviceFingerprint.create(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
            "192.168.1.3"
        )

        # Assert
        assert fingerprint.device_name == "Safari on iOS"


class TestDeviceFingerprintValidation:
    """Tests para validación de DeviceFingerprint"""

    def test_empty_user_agent_rejected(self):
        """
        Test: user_agent vacío es rechazado
        Given: user_agent vacío
        When: Se intenta crear DeviceFingerprint
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DeviceFingerprint.create("", "192.168.1.1")

        assert "User-Agent no puede estar vacío" in str(exc_info.value)

    def test_empty_ip_address_rejected(self):
        """
        Test: ip_address vacío es rechazado
        Given: ip_address vacío
        When: Se intenta crear DeviceFingerprint
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DeviceFingerprint.create("Mozilla/5.0", "")

        assert "IP address no puede estar vacía" in str(exc_info.value)

    def test_whitespace_only_user_agent_rejected(self):
        """
        Test: user_agent solo espacios es rechazado
        Given: user_agent con solo espacios
        When: Se intenta crear DeviceFingerprint
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            DeviceFingerprint.create("   ", "192.168.1.1")

    def test_whitespace_only_ip_rejected(self):
        """
        Test: ip_address solo espacios es rechazado
        Given: ip_address con solo espacios
        When: Se intenta crear DeviceFingerprint
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            DeviceFingerprint.create("Mozilla/5.0", "   ")


class TestDeviceFingerprintIPv6Support:
    """Tests para soporte de IPv6"""

    def test_ipv6_address_accepted(self):
        """
        Test: IPv6 es aceptada
        Given: Dirección IPv6 válida
        When: Se crea DeviceFingerprint
        Then: Se acepta sin errores
        """
        # Arrange
        ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        # Act
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", ipv6)

        # Assert
        assert fingerprint.ip_address == ipv6

    def test_ipv6_shortened_accepted(self):
        """
        Test: IPv6 abreviada es aceptada
        Given: IPv6 en formato corto
        When: Se crea DeviceFingerprint
        Then: Se acepta sin errores
        """
        # Arrange
        ipv6_short = "2001:db8::8a2e:370:7334"

        # Act
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", ipv6_short)

        # Assert
        assert fingerprint.ip_address == ipv6_short

    def test_ipv6_mapped_ipv4_normalized(self):
        """
        Test: IPv6-mapped-IPv4 se normaliza a IPv4
        Given: IPv6-mapped-IPv4 (::ffff:192.168.1.1)
        When: Se crea DeviceFingerprint
        Then: Se normaliza a IPv4 puro (192.168.1.1)
        """
        # Act
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "::ffff:192.168.1.100")

        # Assert
        assert fingerprint.ip_address == "192.168.1.100"


class TestDeviceFingerprintComparison:
    """Tests para comparación de DeviceFingerprint"""

    def test_matches_returns_true_for_same_fingerprint(self):
        """
        Test: matches() retorna True para mismo dispositivo
        Given: Dos DeviceFingerprint con mismos datos
        When: Se comparan con matches()
        Then: Retorna True
        """
        # Arrange
        fp1 = DeviceFingerprint.create("Mozilla/5.0 (Macintosh)", "192.168.1.100")
        fp2 = DeviceFingerprint.create("Mozilla/5.0 (Macintosh)", "192.168.1.100")

        # Act & Assert
        assert fp1.matches(fp2)

    def test_matches_returns_false_for_different_fingerprint(self):
        """
        Test: matches() retorna False para dispositivos diferentes
        Given: Dos DeviceFingerprint con datos distintos
        When: Se comparan con matches()
        Then: Retorna False
        """
        # Arrange
        fp1 = DeviceFingerprint.create("Mozilla/5.0 (Macintosh)", "192.168.1.100")
        fp2 = DeviceFingerprint.create("Mozilla/5.0 (Windows)", "192.168.1.101")

        # Act & Assert
        assert not fp1.matches(fp2)

    def test_equality_operator_works(self):
        """
        Test: Operador == funciona correctamente
        Given: Dos DeviceFingerprint con mismos datos
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        fp1 = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")
        fp2 = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")

        # Act & Assert
        assert fp1 == fp2

    def test_hash_method_allows_dict_usage(self):
        """
        Test: __hash__() permite usar como key de diccionario
        Given: DeviceFingerprint
        When: Se usa como key de dict
        Then: Funciona correctamente
        """
        # Arrange
        fp = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")

        # Act
        fingerprint_dict = {fp: "some_value"}

        # Assert
        assert fingerprint_dict[fp] == "some_value"

    def test_str_returns_device_name(self):
        """
        Test: str() retorna device_name
        Given: DeviceFingerprint con device_name conocido
        When: Se convierte a string
        Then: Retorna el device_name
        """
        # Arrange
        fp = DeviceFingerprint.create(
            "Mozilla/5.0 (Macintosh) Chrome/120.0",
            "192.168.1.1"
        )

        # Act & Assert
        assert str(fp) == "Chrome on macOS"

    def test_repr_contains_device_name_and_hash(self):
        """
        Test: repr() contiene device_name y hash truncado
        Given: DeviceFingerprint
        When: Se obtiene repr()
        Then: Contiene device_name y hash preview
        """
        # Arrange
        fp = DeviceFingerprint.create("Mozilla/5.0 (Macintosh)", "192.168.1.1")

        # Act
        repr_str = repr(fp)

        # Assert
        assert "DeviceFingerprint" in repr_str
        assert "device_name=" in repr_str
        assert "hash=" in repr_str


class TestDeviceFingerprintImmutability:
    """Tests para inmutabilidad de DeviceFingerprint"""

    def test_fingerprint_is_frozen(self):
        """
        Test: DeviceFingerprint es inmutable (frozen dataclass)
        Given: DeviceFingerprint creado
        When: Se intenta modificar un campo
        Then: Lanza FrozenInstanceError
        """
        # Arrange
        fp = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")

        # Act & Assert
        with pytest.raises(Exception):  # FrozenInstanceError o AttributeError
            fp.device_name = "New Name"  # type: ignore
