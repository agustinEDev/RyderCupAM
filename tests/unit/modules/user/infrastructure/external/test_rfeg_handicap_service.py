"""
Tests unitarios para RFEGHandicapService

Verifica la funcionalidad de normalización de texto para eliminar acentos.
"""

from src.modules.user.infrastructure.external.rfeg_handicap_service import RFEGHandicapService


class TestRFEGHandicapServiceNormalizacion:
    """Tests para la normalización de texto"""

    def test_normalizar_texto_con_acentos(self):
        """Debe eliminar acentos de caracteres españoles"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Agustín")

        # Assert
        assert resultado == "Agustin"

    def test_normalizar_texto_con_multiples_acentos(self):
        """Debe eliminar todos los acentos de un nombre completo"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("José María López García")

        # Assert
        assert resultado == "Jose Maria Lopez Garcia"

    def test_normalizar_texto_sin_acentos(self):
        """No debe modificar texto que ya no tiene acentos"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Juan Carlos Perez")

        # Assert
        assert resultado == "Juan Carlos Perez"

    def test_normalizar_texto_con_enie(self):
        """Debe normalizar la ñ a n (NFD descompone todos los diacríticos)"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Peña")

        # Assert
        assert resultado == "Pena"

    def test_normalizar_texto_vacio(self):
        """Debe manejar string vacío"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("")

        # Assert
        assert resultado == ""

    def test_normalizar_texto_con_dieresis(self):
        """Debe eliminar diéresis"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Güell")

        # Assert
        assert resultado == "Guell"

    def test_normalizar_texto_con_espacios_extra(self):
        """Debe eliminar espacios extra al principio, al final y entre palabras"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("  José   Buela  Fernández  ")

        # Assert
        assert resultado == "Jose Buela Fernandez"
