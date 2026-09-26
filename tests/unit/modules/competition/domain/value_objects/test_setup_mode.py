"""
El modo de configuración de una competición (FE #695).

Decidido el 22 sep: la decisión se mueve al principio. Al crear el torneo se
elige cuánto hace la aplicación por su cuenta, y eso decide qué pasos existen
después.
"""

import pytest

from src.modules.competition.domain.value_objects.setup_mode import SetupMode


class TestSetupMode:
    def test_son_tres_modos(self):
        """Ni uno más: cada uno es una forma entera de montar el torneo."""
        assert [m.value for m in SetupMode] == ["AUTOMATIC", "MANUAL", "RYDER_CUP"]

    @pytest.mark.parametrize("texto", ["AUTOMATIC", "MANUAL", "RYDER_CUP"])
    def test_se_reconstruye_desde_su_texto(self, texto):
        """Es lo que llega de la base y de la API."""
        assert SetupMode(texto).value == texto

    def test_un_modo_que_no_existe(self):
        with pytest.raises(ValueError):
            SetupMode("SEMIAUTOMATIC")

    def test_se_escribe_con_su_texto(self):
        """El DTO lo manda como cadena."""
        assert str(SetupMode.RYDER_CUP) == "RYDER_CUP"
