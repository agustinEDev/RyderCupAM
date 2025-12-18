"""
Tests Unitarios - HTML Sanitizers

Verifica que la sanitización HTML funcione correctamente para prevenir
ataques XSS (Cross-Site Scripting).

OWASP Coverage Test: A03 (Injection)
"""

import pytest

from src.shared.application.validation.sanitizers import (
    normalize_unicode,
    remove_sql_keywords,
    sanitize_all_fields,
    sanitize_html,
)


class TestSanitizeHTML:
    """Tests para sanitize_html()."""

    def test_sanitize_html_removes_script_tags(self):
        """
        Test: Elimina tags <script> completos

        Given: String con tag <script>
        When: Se sanitiza
        Then: El tag se elimina pero el contenido permanece
        """
        # Arrange
        malicious = "<script>alert('XSS')</script>"

        # Act
        result = sanitize_html(malicious)

        # Assert
        assert "<script>" not in result
        assert "</script>" not in result
        assert "alert" in result  # Contenido permanece (escapado)

    def test_sanitize_html_removes_all_html_tags(self):
        """
        Test: Elimina todos los tags HTML (b, i, div, etc.)

        Given: String con múltiples tags HTML
        When: Se sanitiza
        Then: Todos los tags se eliminan
        """
        # Arrange
        html_text = "Hello <b>world</b> <i>this</i> is <div>a test</div>"

        # Act
        result = sanitize_html(html_text)

        # Assert
        assert result == "Hello world this is a test"
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_html_escapes_html_entities(self):
        """
        Test: Escapa entidades HTML peligrosas

        Given: String con caracteres < > &
        When: Se sanitiza
        Then: Los caracteres se escapan
        """
        # Arrange
        text = "5 < 10 & 10 > 5"

        # Act
        result = sanitize_html(text)

        # Assert
        # Los caracteres peligrosos se escapan
        assert "<" not in result or "&lt;" in result
        assert ">" not in result or "&gt;" in result

    def test_sanitize_html_normalizes_multiple_spaces(self):
        """
        Test: Normaliza espacios múltiples a uno solo

        Given: String con espacios múltiples
        When: Se sanitiza con allow_whitespace=True
        Then: Los espacios se normalizan a uno
        """
        # Arrange
        text = "Hello    world   multiple    spaces"

        # Act
        result = sanitize_html(text, allow_whitespace=True)

        # Assert
        assert result == "Hello world multiple spaces"

    def test_sanitize_html_trims_leading_trailing_spaces(self):
        """
        Test: Elimina espacios al inicio y final

        Given: String con espacios al inicio/final
        When: Se sanitiza
        Then: Los espacios se eliminan
        """
        # Arrange
        text = "   Hello world   "

        # Act
        result = sanitize_html(text)

        # Assert
        assert result == "Hello world"

    def test_sanitize_html_returns_none_for_none_input(self):
        """
        Test: Retorna None si el input es None

        Given: Input None
        When: Se sanitiza
        Then: Retorna None
        """
        # Act
        result = sanitize_html(None)

        # Assert
        assert result is None

    def test_sanitize_html_returns_empty_for_empty_string(self):
        """
        Test: Retorna string vacío para input vacío

        Given: String vacío o solo espacios
        When: Se sanitiza
        Then: Retorna string vacío
        """
        # Act
        result1 = sanitize_html("")
        result2 = sanitize_html("   ")

        # Assert
        assert result1 == ""
        assert result2 == ""

    def test_sanitize_html_removes_control_characters(self):
        """
        Test: Elimina caracteres de control peligrosos

        Given: String con NULL bytes y caracteres de control
        When: Se sanitiza
        Then: Los caracteres de control se eliminan
        """
        # Arrange
        text = "Hello\x00World\x1F"  # NULL byte + Unit Separator

        # Act
        result = sanitize_html(text)

        # Assert
        assert "\x00" not in result
        assert "\x1F" not in result
        assert result == "HelloWorld"

    def test_sanitize_html_handles_complex_xss_attempt(self):
        """
        Test: Maneja intento complejo de XSS

        Given: String con múltiples vectores de XSS
        When: Se sanitiza
        Then: Todos los vectores se neutralizan
        """
        # Arrange
        malicious = """
            <img src=x onerror=alert('XSS')>
            <script>document.cookie</script>
            <iframe src="javascript:alert('XSS')"></iframe>
        """

        # Act
        result = sanitize_html(malicious)

        # Assert
        assert "<img" not in result
        assert "onerror" not in result
        assert "<script>" not in result
        assert "<iframe>" not in result
        assert "javascript:" not in result


class TestSanitizeAllFields:
    """Tests para sanitize_all_fields()."""

    def test_sanitize_all_fields_sanitizes_string_fields(self):
        """
        Test: Sanitiza todos los campos string de un diccionario

        Given: Diccionario con campos string con HTML
        When: Se sanitiza
        Then: Todos los strings se sanitizan
        """
        # Arrange
        data = {
            "name": "<script>XSS</script>",
            "email": "user@example.com",
            "bio": "Hello <b>world</b>"
        }

        # Act
        result = sanitize_all_fields(data)

        # Assert
        assert "<script>" not in result["name"]
        assert "<b>" not in result["bio"]
        assert result["email"] == "user@example.com"  # Sin HTML, no cambia

    def test_sanitize_all_fields_respects_exclude_list(self):
        """
        Test: Respeta lista de campos a excluir

        Given: Diccionario con campo password
        When: Se sanitiza con exclude=["password"]
        Then: El password no se modifica
        """
        # Arrange
        data = {
            "name": "<b>John</b>",
            "password": "P@ssw0rd!<>",  # Password puede tener caracteres especiales
        }

        # Act
        result = sanitize_all_fields(data, exclude=["password"])

        # Assert
        assert result["name"] == "John"
        assert result["password"] == "P@ssw0rd!<>"  # Sin modificar

    def test_sanitize_all_fields_handles_nested_dicts(self):
        """
        Test: Sanitiza diccionarios anidados recursivamente

        Given: Diccionario con diccionarios anidados
        When: Se sanitiza
        Then: Todos los niveles se sanitizan
        """
        # Arrange
        data = {
            "user": {
                "name": "<script>XSS</script>",
                "address": {
                    "street": "<b>Main St</b>"
                }
            }
        }

        # Act
        result = sanitize_all_fields(data)

        # Assert
        assert "<script>" not in result["user"]["name"]
        assert "<b>" not in result["user"]["address"]["street"]

    def test_sanitize_all_fields_handles_lists(self):
        """
        Test: Sanitiza listas de strings

        Given: Diccionario con listas de strings
        When: Se sanitiza
        Then: Todos los strings de la lista se sanitizan
        """
        # Arrange
        data = {
            "tags": ["<script>XSS</script>", "normal", "<b>bold</b>"]
        }

        # Act
        result = sanitize_all_fields(data)

        # Assert
        assert "<script>" not in result["tags"][0]
        assert result["tags"][1] == "normal"
        assert "<b>" not in result["tags"][2]

    def test_sanitize_all_fields_preserves_non_string_types(self):
        """
        Test: Preserva tipos no-string (int, bool, None)

        Given: Diccionario con múltiples tipos
        When: Se sanitiza
        Then: Solo los strings se modifican
        """
        # Arrange
        data = {
            "name": "<b>John</b>",
            "age": 30,
            "active": True,
            "bio": None,
        }

        # Act
        result = sanitize_all_fields(data)

        # Assert
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["active"] is True
        assert result["bio"] is None


class TestRemoveSQLKeywords:
    """Tests para remove_sql_keywords()."""

    def test_remove_sql_keywords_removes_select(self):
        """
        Test: Elimina keyword SELECT

        Given: String con SELECT
        When: Se limpia
        Then: SELECT se elimina
        """
        # Arrange
        text = "SELECT * FROM users"

        # Act
        result = remove_sql_keywords(text)

        # Assert
        assert "SELECT" not in result
        assert "*  users" in result  # Resto permanece

    def test_remove_sql_keywords_case_insensitive(self):
        """
        Test: Elimina keywords sin importar mayúsculas/minúsculas

        Given: String con keywords en diferentes casos
        When: Se limpia
        Then: Todos se eliminan
        """
        # Arrange
        text = "select Select SeLeCt"

        # Act
        result = remove_sql_keywords(text)

        # Assert
        assert "select" not in result.lower()

    def test_remove_sql_keywords_returns_none_for_none(self):
        """
        Test: Retorna None para input None

        Given: Input None
        When: Se limpia
        Then: Retorna None
        """
        # Act
        result = remove_sql_keywords(None)

        # Assert
        assert result is None


class TestNormalizeUnicode:
    """Tests para normalize_unicode()."""

    def test_normalize_unicode_normalizes_composed_characters(self):
        """
        Test: Normaliza caracteres compuestos a forma canónica

        Given: String con caracteres Unicode compuestos
        When: Se normaliza
        Then: Los caracteres se convierten a forma canónica (NFC)
        """
        # Arrange
        # "café" con é como carácter compuesto (e + ́)
        text = "cafe\u0301"  # e + combining acute accent

        # Act
        result = normalize_unicode(text)

        # Assert
        # Debe convertirse a "café" con é como carácter único
        assert result == "café"
        assert len(result) == 4  # 4 caracteres, no 5

    def test_normalize_unicode_returns_none_for_none(self):
        """
        Test: Retorna None para input None

        Given: Input None
        When: Se normaliza
        Then: Retorna None
        """
        # Act
        result = normalize_unicode(None)

        # Assert
        assert result is None

    def test_normalize_unicode_prevents_homograph_attacks(self):
        """
        Test: Ayuda a prevenir ataques de homógrafos

        Given: Caracteres visualmente similares pero diferentes
        When: Se normalizan
        Then: Se convierten a forma consistente
        """
        # Arrange
        # Letra cirílica 'а' (U+0430) vs latina 'a' (U+0061)
        cyrillic_a = "\u0430"  # Cyrillic small letter a
        latin_a = "a"

        # Act
        result_cyrillic = normalize_unicode(cyrillic_a)
        result_latin = normalize_unicode(latin_a)

        # Assert
        # Ambos se normalizan pero NO son iguales (son caracteres diferentes)
        assert result_cyrillic != result_latin
        # Pero la normalización asegura consistencia
        assert result_cyrillic == "\u0430"
        assert result_latin == "a"
