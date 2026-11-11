"""
Tests Unitarios - Custom Validators

Verifica que los validadores personalizados funcionen correctamente.

OWASP Coverage Test: A03 (Injection), A07 (Authentication Failures)
"""

import pytest

from src.shared.application.validation.validators import (
    AliasValidator,
    NameValidator,
)


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


class TestAliasValidator:
    """Tests para AliasValidator (alias público del perfil, BE #239)."""

    def test_validate_accepts_simple_alias(self):
        """
        Test: Acepta un alias corriente

        Given: El alias "Chuchi"
        When: Se valida
        Then: Se devuelve tal cual, sin cambiar mayúsculas
        """
        assert AliasValidator.validate("Chuchi") == "Chuchi"

    def test_validate_preserves_case(self):
        """
        Test: No normaliza mayúsculas

        Given: El alias "ChuChi"
        When: Se valida
        Then: Se conserva como se escribió — la unicidad la resuelve el
              índice de la base de datos ignorando mayúsculas, no el
              validador cambiando lo que la persona escribió
        """
        assert AliasValidator.validate("ChuChi") == "ChuChi"

    def test_validate_accepts_digits_and_allowed_signs(self):
        """
        Test: Acepta dígitos, punto, guion bajo y guion

        Given: Aliases con números y los signos permitidos
        When: Se validan
        Then: Se aceptan
        """
        for alias in ("Peña_23", "j.garcia", "el-cangrejo", "Tiger 18"):
            assert AliasValidator.validate(alias) == alias

    def test_validate_accepts_accents(self):
        """
        Test: Acepta acentos y eñes

        Given: El alias "Muñóz"
        When: Se valida
        Then: Se acepta
        """
        assert AliasValidator.validate("Muñóz") == "Muñóz"

    def test_validate_trims_and_collapses_inner_spaces(self):
        """
        Test: Normaliza espacios

        Given: El alias "  Chu  chi  "
        When: Se valida
        Then: Queda "Chu chi" — si no se colapsan los espacios internos,
              "Chu  chi" y "Chu chi" serían dos aliases distintos y el
              índice único no los vería como el mismo
        """
        assert AliasValidator.validate("  Chu  chi  ") == "Chu chi"

    def test_validate_rejects_one_character(self):
        """
        Test: Rechaza un alias de un solo carácter

        Given: El alias "C"
        When: Se valida
        Then: ValueError — el autocompletado necesita 2 caracteres para
              disparar la búsqueda, así que uno solo sería inencontrable
        """
        with pytest.raises(ValueError, match="al menos 2 caracteres"):
            AliasValidator.validate("C")

    def test_validate_rejects_more_than_twenty_characters(self):
        """
        Test: Rechaza un alias de más de 20 caracteres

        Given: Un alias de 21 caracteres
        When: Se valida
        Then: ValueError
        """
        with pytest.raises(ValueError, match="no puede exceder 20 caracteres"):
            AliasValidator.validate("a" * 21)

    def test_validate_accepts_the_length_bounds(self):
        """
        Test: Los límites son inclusivos

        Given: Aliases de exactamente 2 y 20 caracteres
        When: Se validan
        Then: Los dos se aceptan
        """
        assert AliasValidator.validate("ab") == "ab"
        assert AliasValidator.validate("a" * 20) == "a" * 20

    @pytest.mark.parametrize(
        "alias",
        [
            "Chu<b>chi",
            "<script>alert(1)</script>",
            "Chuchi🏌",
            "chu@chi",
            "chu/chi",
            "chu#chi",
        ],
    )
    def test_validate_rejects_html_emoji_and_other_signs(self, alias):
        """
        Test: Rechaza HTML, emoji y signos fuera de la lista

        Given: Aliases con marcado, emoji o signos no permitidos
        When: Se validan
        Then: ValueError
        """
        with pytest.raises(ValueError):
            AliasValidator.validate(alias)

    def test_validate_rejects_multiplication_and_division_signs(self):
        """
        Test: Rechaza los signos de multiplicar y dividir

        Given: Aliases con U+00D7 y U+00F7, que caen dentro del rango
               `À-ÿ` que usa NameValidator sin ser letras
        When: Se validan
        Then: ValueError — este validador se salta los dos a propósito en
              vez de heredar ese fallo
        """
        for alias in ("chu\u00d7chi", "chu\u00f7chi"):
            with pytest.raises(ValueError):
                AliasValidator.validate(alias)

    def test_validate_rejects_only_signs(self):
        """
        Test: Rechaza un alias sin letras ni números

        Given: El alias "..."
        When: Se valida
        Then: ValueError — no identifica a nadie y no se puede buscar por él
        """
        with pytest.raises(ValueError, match="al menos una letra o un número"):
            AliasValidator.validate("...")

    def test_validate_rejects_empty(self):
        """
        Test: Rechaza la cadena vacía

        Given: Un alias vacío
        When: Se valida
        Then: ValueError — vaciar el alias es cosa del DTO, que lo traduce
              a NULL sin pasar por aquí
        """
        with pytest.raises(ValueError, match="no puede estar vacío"):
            AliasValidator.validate("")
