"""
Tests Unitarios - Custom Validators

Verifica que los validadores personalizados funcionen correctamente.

OWASP Coverage Test: A03 (Injection), A07 (Authentication Failures)
"""

import pytest

from src.shared.application.validation.validators import (
    EmailValidator,
    NameValidator,
    validate_country_code,
    validate_email_strict,
    validate_no_script_tags,
)


class TestEmailValidator:
    """Tests para EmailValidator."""

    def test_validate_accepts_valid_email(self):
        """
        Test: Acepta email válido estándar

        Given: Email válido "user@example.com"
        When: Se valida
        Then: Retorna el email normalizado
        """
        # Act
        result = EmailValidator.validate("user@example.com")

        # Assert
        assert result == "user@example.com"

    def test_validate_normalizes_to_lowercase(self):
        """
        Test: Normaliza emails a minúsculas

        Given: Email con mayúsculas
        When: Se valida
        Then: Retorna email en minúsculas
        """
        # Act
        result = EmailValidator.validate("USER@EXAMPLE.COM")

        # Assert
        assert result == "user@example.com"

    def test_validate_trims_whitespace(self):
        """
        Test: Elimina espacios al inicio/final

        Given: Email con espacios
        When: Se valida
        Then: Retorna email sin espacios
        """
        # Act
        result = EmailValidator.validate("  user@example.com  ")

        # Assert
        assert result == "user@example.com"

    def test_validate_rejects_email_without_at(self):
        """
        Test: Rechaza email sin @

        Given: Email sin @
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            EmailValidator.validate("userexample.com")

        assert "Formato de email inválido" in str(exc_info.value)

    def test_validate_rejects_email_without_dot(self):
        """
        Test: Rechaza email sin punto en dominio

        Given: Email sin TLD (user@domain)
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            EmailValidator.validate("user@domain")

        assert "TLD" in str(exc_info.value) or "Formato de email inválido" in str(
            exc_info.value
        )

    def test_validate_rejects_too_long_email(self):
        """
        Test: Rechaza email que excede 254 caracteres

        Given: Email con 255+ caracteres
        When: Se valida
        Then: Lanza ValueError
        """
        # Arrange
        long_email = "a" * 250 + "@example.com"  # ~260 caracteres

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            EmailValidator.validate(long_email)

        assert "254 caracteres" in str(exc_info.value)

    def test_validate_rejects_too_short_email(self):
        """
        Test: Rechaza email demasiado corto

        Given: Email con menos de 5 caracteres
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            EmailValidator.validate("a@b")

        assert "5 caracteres" in str(exc_info.value)

    def test_validate_rejects_empty_email(self):
        """
        Test: Rechaza email vacío

        Given: String vacío
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            EmailValidator.validate("")

        assert "vacío" in str(exc_info.value)

    def test_validate_accepts_email_with_subdomain(self):
        """
        Test: Acepta email con subdominios

        Given: Email con subdominios
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = EmailValidator.validate("user@mail.example.com")

        # Assert
        assert result == "user@mail.example.com"

    def test_validate_accepts_email_with_dots_and_plus(self):
        """
        Test: Acepta email con puntos y + en local part

        Given: Email con caracteres especiales permitidos
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result1 = EmailValidator.validate("first.last@example.com")
        result2 = EmailValidator.validate("user+tag@example.com")

        # Assert
        assert result1 == "first.last@example.com"
        assert result2 == "user+tag@example.com"

    def test_validate_rejects_local_part_too_long(self):
        """
        Test: Rechaza local part que excede 64 caracteres

        Given: Email con local part de 65+ caracteres
        When: Se valida
        Then: Lanza ValueError
        """
        # Arrange
        long_local = "a" * 65 + "@example.com"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            EmailValidator.validate(long_local)

        assert "64 caracteres" in str(exc_info.value)

    def test_is_valid_returns_true_for_valid_email(self):
        """
        Test: is_valid() retorna True para email válido

        Given: Email válido
        When: Se verifica con is_valid()
        Then: Retorna True
        """
        # Act
        result = EmailValidator.is_valid("user@example.com")

        # Assert
        assert result is True

    def test_is_valid_returns_false_for_invalid_email(self):
        """
        Test: is_valid() retorna False para email inválido

        Given: Email inválido
        When: Se verifica con is_valid()
        Then: Retorna False (sin lanzar excepción)
        """
        # Act
        result = EmailValidator.is_valid("invalid")

        # Assert
        assert result is False


class TestValidateEmailStrict:
    """Tests para validate_email_strict()."""

    def test_validate_email_strict_calls_email_validator(self):
        """
        Test: Llama a EmailValidator.validate()

        Given: Email válido
        When: Se valida con validate_email_strict()
        Then: Retorna email normalizado
        """
        # Act
        result = validate_email_strict("USER@EXAMPLE.COM")

        # Assert
        assert result == "user@example.com"

    def test_validate_email_strict_rejects_non_string(self):
        """
        Test: Rechaza inputs que no son string

        Given: Input que no es string (int, bool, etc.)
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_email_strict(123)

        assert "debe ser un string" in str(exc_info.value)


class TestNameValidator:
    """Tests para NameValidator."""

    def test_validate_accepts_simple_name(self):
        """
        Test: Acepta nombre simple

        Given: Nombre válido "John"
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = NameValidator.validate("John")

        # Assert
        assert result == "John"

    def test_validate_accepts_name_with_accents(self):
        """
        Test: Acepta nombres con acentos

        Given: Nombre con acentos "José María"
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = NameValidator.validate("José María")

        # Assert
        assert result == "José María"

    def test_validate_accepts_name_with_hyphen(self):
        """
        Test: Acepta nombres con guión

        Given: Nombre compuesto "Jean-Pierre"
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = NameValidator.validate("Jean-Pierre")

        # Assert
        assert result == "Jean-Pierre"

    def test_validate_accepts_name_with_apostrophe(self):
        """
        Test: Acepta nombres con apóstrofe

        Given: Nombre con apóstrofe "O'Connor"
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = NameValidator.validate("O'Connor")

        # Assert
        assert result == "O'Connor"

    def test_validate_rejects_name_with_numbers(self):
        """
        Test: Rechaza nombres con números

        Given: Nombre con números "John123"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            NameValidator.validate("John123")

        assert "solo puede contener letras" in str(exc_info.value)

    def test_validate_rejects_name_with_special_chars(self):
        """
        Test: Rechaza nombres con caracteres especiales

        Given: Nombre con @ "John@Doe"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            NameValidator.validate("John@Doe")

        assert "solo puede contener letras" in str(exc_info.value)

    def test_validate_rejects_too_short_name(self):
        """
        Test: Rechaza nombre demasiado corto

        Given: Nombre con 1 carácter
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            NameValidator.validate("J")

        assert "al menos 2 caracteres" in str(exc_info.value)

    def test_validate_rejects_too_long_name(self):
        """
        Test: Rechaza nombre demasiado largo

        Given: Nombre con 101+ caracteres
        When: Se valida
        Then: Lanza ValueError
        """
        # Arrange
        long_name = "a" * 101

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            NameValidator.validate(long_name)

        assert "100 caracteres" in str(exc_info.value)

    def test_validate_trims_whitespace(self):
        """
        Test: Elimina espacios al inicio/final

        Given: Nombre con espacios "  John  "
        When: Se valida
        Then: Retorna nombre sin espacios
        """
        # Act
        result = NameValidator.validate("  John  ")

        # Assert
        assert result == "John"

    def test_validate_rejects_only_spaces_or_hyphens(self):
        """
        Test: Rechaza nombres que solo tienen espacios/guiones

        Given: Nombre "---" o "   "
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            NameValidator.validate("---")

        assert "al menos una letra" in str(exc_info.value)


class TestValidateCountryCode:
    """Tests para validate_country_code()."""

    def test_validate_country_code_accepts_valid_code(self):
        """
        Test: Acepta código ISO válido

        Given: Código válido "ES"
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = validate_country_code("ES")

        # Assert
        assert result == "ES"

    def test_validate_country_code_normalizes_to_uppercase(self):
        """
        Test: Normaliza a mayúsculas

        Given: Código en minúsculas "es"
        When: Se valida
        Then: Retorna en mayúsculas "ES"
        """
        # Act
        result = validate_country_code("es")

        # Assert
        assert result == "ES"

    def test_validate_country_code_returns_none_for_none(self):
        """
        Test: Retorna None para input None

        Given: Input None
        When: Se valida
        Then: Retorna None
        """
        # Act
        result = validate_country_code(None)

        # Assert
        assert result is None

    def test_validate_country_code_rejects_wrong_length(self):
        """
        Test: Rechaza códigos con longitud incorrecta

        Given: Código con 3 letras "ESP"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_country_code("ESP")

        assert "2 letras" in str(exc_info.value)

    def test_validate_country_code_rejects_numbers(self):
        """
        Test: Rechaza códigos con números

        Given: Código "E1"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_country_code("E1")

        assert "solo puede contener letras" in str(exc_info.value)


class TestValidateNoScriptTags:
    """Tests para validate_no_script_tags()."""

    def test_validate_no_script_tags_accepts_clean_text(self):
        """
        Test: Acepta texto sin scripts

        Given: Texto limpio "Hello world"
        When: Se valida
        Then: Es aceptado
        """
        # Act
        result = validate_no_script_tags("Hello world")

        # Assert
        assert result == "Hello world"

    def test_validate_no_script_tags_rejects_script_tag(self):
        """
        Test: Rechaza texto con tag <script>

        Given: Texto con "<script>"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_no_script_tags("<script>alert(1)</script>")

        assert "contenido no permitido" in str(exc_info.value)

    def test_validate_no_script_tags_rejects_javascript_protocol(self):
        """
        Test: Rechaza texto con javascript:

        Given: Texto con "javascript:"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_no_script_tags("javascript:alert(1)")

        assert "contenido no permitido" in str(exc_info.value)

    def test_validate_no_script_tags_rejects_event_handlers(self):
        """
        Test: Rechaza texto con event handlers (onerror, onclick, etc.)

        Given: Texto con "onerror="
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_no_script_tags('img onerror="alert(1)"')

        assert "contenido no permitido" in str(exc_info.value)

    def test_validate_no_script_tags_case_insensitive(self):
        """
        Test: Detección case-insensitive

        Given: Texto con "<SCRIPT>"
        When: Se valida
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            validate_no_script_tags("<SCRIPT>alert(1)</SCRIPT>")

    def test_validate_no_script_tags_handles_empty_string(self):
        """
        Test: Maneja string vacío correctamente

        Given: String vacío
        When: Se valida
        Then: Retorna string vacío sin error
        """
        # Act
        result = validate_no_script_tags("")

        # Assert
        assert result == ""
