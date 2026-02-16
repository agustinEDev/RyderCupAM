"""
Tests unitarios para el Value Object OAuthProvider.

Este archivo contiene tests que verifican:
- Valores del enum
- Comportamiento de StrEnum
- Comparación de valores
"""

from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider


class TestOAuthProviderEnum:
    """Tests para el enum OAuthProvider"""

    def test_google_value(self):
        """
        Test: GOOGLE tiene el valor correcto
        Given: Enum OAuthProvider
        When: Se accede a GOOGLE
        Then: El valor es "google"
        """
        # Act & Assert
        assert OAuthProvider.GOOGLE == "google"
        assert OAuthProvider.GOOGLE.value == "google"

    def test_google_is_str_enum(self):
        """
        Test: OAuthProvider.GOOGLE es StrEnum
        Given: OAuthProvider.GOOGLE
        When: Se verifica tipo
        Then: Es instancia de str y OAuthProvider
        """
        # Act & Assert
        assert isinstance(OAuthProvider.GOOGLE, str)
        assert isinstance(OAuthProvider.GOOGLE, OAuthProvider)

    def test_enum_comparison(self):
        """
        Test: Comparación de valores enum
        Given: OAuthProvider.GOOGLE
        When: Se compara con string "google"
        Then: Son iguales (StrEnum behavior)
        """
        # Act & Assert
        assert OAuthProvider.GOOGLE == "google"
        assert OAuthProvider.GOOGLE == "google"

    def test_string_value_matches(self):
        """
        Test: Valor string del enum
        Given: OAuthProvider.GOOGLE
        When: Se convierte a string
        Then: Retorna "google"
        """
        # Act
        provider_str = str(OAuthProvider.GOOGLE)

        # Assert
        assert provider_str == "google"
