"""
Tests Unitarios - HTML Sanitizers

Verifica que la sanitización HTML funcione correctamente para prevenir
ataques XSS (Cross-Site Scripting).

OWASP Coverage Test: A03 (Injection)
"""

from src.shared.application.validation.sanitizers import (
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
        text = "Hello\x00World\x1f"  # NULL byte + Unit Separator

        # Act
        result = sanitize_html(text)

        # Assert
        assert "\x00" not in result
        assert "\x1f" not in result
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
