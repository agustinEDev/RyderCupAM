"""
Buscar la barra de un jugador por color y género (RyderCupAM#165).

Un campo federado valora la misma barra por separado para cada género, y un
campo dado de alta a mano puede tenerla sin género. La regla: primero
(color, género) y, si no está, (color, sin género). Estaba escrita siete veces
—cinco devolviendo el valor y dos la barra encontrada—, entre competición y
partida rápida.
"""

from src.shared.domain.services.tee_lookup import find_tee, tee_key_for

VALORACIONES = {
    ("YELLOW", "MALE"): "amarillas de hombre",
    ("YELLOW", "FEMALE"): "amarillas de mujer",
    ("RED", None): "rojas sin género",
}


class TestTeeKeyFor:
    """La barra que se usa: hace falta para guardar el género con el que se jugó."""

    def test_la_barra_de_su_genero(self):
        assert tee_key_for(VALORACIONES, "YELLOW", "MALE") == ("YELLOW", "MALE")

    def test_sin_la_de_su_genero_la_barra_sin_genero(self):
        assert tee_key_for(VALORACIONES, "RED", "FEMALE") == ("RED", None)

    def test_sin_genero_conocido_la_barra_sin_genero(self):
        assert tee_key_for(VALORACIONES, "RED", None) == ("RED", None)

    def test_la_del_otro_genero_no_sirve(self):
        """Una barra de mujer no se le da a un hombre: valen varios golpes de diferencia."""
        assert tee_key_for({("YELLOW", "FEMALE"): 1}, "YELLOW", "MALE") is None

    def test_un_color_que_no_esta(self):
        assert tee_key_for(VALORACIONES, "BLUE", "MALE") is None


class TestFindTee:
    def test_devuelve_el_valor_de_la_barra_encontrada(self):
        assert find_tee(VALORACIONES, "YELLOW", "FEMALE") == "amarillas de mujer"

    def test_con_la_reserva_sin_genero(self):
        assert find_tee(VALORACIONES, "RED", "MALE") == "rojas sin género"

    def test_sin_barra_devuelve_el_por_defecto(self):
        """El orden de hoyos cae al del campo cuando la barra no trae tarjeta propia."""
        assert find_tee(VALORACIONES, "BLUE", "MALE", default="del campo") == "del campo"

    def test_sin_barra_y_sin_por_defecto_es_none(self):
        assert find_tee(VALORACIONES, "BLUE", "MALE") is None


AMBAS = {("YELLOW", "MALE"): "de hombre", ("YELLOW", None): "sin género"}


class TestConLasDosBarras:
    """Cuando el campo tiene la de su género Y la sin género, gana la de su género."""

    def test_tee_key_for_elige_la_de_su_genero(self):
        assert tee_key_for(AMBAS, "YELLOW", "MALE") == ("YELLOW", "MALE")

    def test_find_tee_elige_la_de_su_genero(self):
        assert find_tee(AMBAS, "YELLOW", "MALE") == "de hombre"
