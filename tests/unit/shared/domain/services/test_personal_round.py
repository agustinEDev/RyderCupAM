"""
El hándicap de juego de la vuelta propia (`personal_playing_handicap`): al 100 %
para las estadísticas y con el allowance de la modalidad para el historial
(Agustín, 24 oct 2026).
"""

from decimal import Decimal

from src.shared.domain.services.personal_round import personal_playing_handicap
from src.shared.domain.services.playing_handicap_calculator import TeeRating

BLANCAS = TeeRating(course_rating=Decimal("72"), slope_rating=130, par=72)


def test_sin_indice_no_hay_handicap():
    assert personal_playing_handicap(None, BLANCAS) is None


def test_a_scratch_cero():
    assert personal_playing_handicap(18, BLANCAS, scratch=True, allowance=90) == 0


def test_con_barra_al_100_por_defecto():
    """18 en blancas: 20,7 de campo, 21 de juego."""
    assert personal_playing_handicap(18, BLANCAS) == 21


def test_con_barra_y_allowance():
    """Al 90 %: 18,6, 19 de juego."""
    assert personal_playing_handicap(18, BLANCAS, allowance=90) == 19


def test_sin_barra_el_indice_al_100_por_defecto():
    assert personal_playing_handicap(20, None) == 20


def test_sin_barra_el_indice_con_el_allowance():
    """20 al 95 %: 19. Como la partida con quien no tiene barra."""
    assert personal_playing_handicap(20, None, allowance=95) == 19


def test_sin_barra_un_plus_sigue_siendo_plus():
    assert personal_playing_handicap(-2, None, allowance=90) == -2
