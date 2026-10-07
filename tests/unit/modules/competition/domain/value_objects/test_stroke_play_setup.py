"""Lo que es solo del stroke play: categorías, jornadas por jugador y la general (#251).

Decidido con Agustín el 6 oct 2026: las categorías son límites superiores de
hándicap (12,0 y 26,0 → «hasta 12,0», «de 12,1 a 26,0», «más de 26,0»), hasta
cinco categorías; cada jugador juega como mucho una franja por jornada y el
organizador fija en cuántas jornadas (normalmente una); la general es
acumulada o mejor tarjeta, a elección del organizador.
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.value_objects.overall_standing import OverallStanding
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
    StrokePlaySetup,
)


def _d(*valores: str) -> list[Decimal]:
    return [Decimal(v) for v in valores]


class TestPorDefecto:
    def test_sin_ajustes_no_hay_categorias_se_juega_una_jornada_y_la_general_acumula(self):
        ajustes = StrokePlaySetup.create()

        assert ajustes.category_limits == ()
        assert ajustes.max_matchdays_per_player == 1
        assert ajustes.overall_standing is OverallStanding.ACCUMULATED


class TestCategorias:
    def test_dos_limites_son_tres_categorias(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0", "26.0"))

        assert ajustes.category_limits == (Decimal("12.0"), Decimal("26.0"))
        assert ajustes.number_of_categories == 3

    def test_sin_limites_hay_una_sola_categoria(self):
        assert StrokePlaySetup.create().number_of_categories == 1

    def test_cuatro_limites_son_cinco_categorias_y_es_el_maximo(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("5.0", "12.0", "20.0", "28.0"))

        assert ajustes.number_of_categories == 5

    def test_cinco_limites_son_demasiadas_categorias(self):
        with pytest.raises(StrokePlaySettingsError, match="5 categorías"):
            StrokePlaySetup.create(category_limits=_d("5.0", "12.0", "20.0", "28.0", "36.0"))

    def test_desordenados_se_rechazan_diciendo_que_van_de_menor_a_mayor(self):
        with pytest.raises(StrokePlaySettingsError, match="de menor a mayor"):
            StrokePlaySetup.create(category_limits=_d("26.0", "12.0"))

    def test_repetidos_se_rechazan(self):
        with pytest.raises(StrokePlaySettingsError, match="de menor a mayor"):
            StrokePlaySetup.create(category_limits=_d("12.0", "12.0"))

    @pytest.mark.parametrize("fuera", ["-10.1", "54.1"])
    def test_fuera_del_rango_de_handicap_se_rechaza(self, fuera):
        with pytest.raises(StrokePlaySettingsError, match="entre -10,0 y 54,0"):
            StrokePlaySetup.create(category_limits=_d(fuera))

    @pytest.mark.parametrize("borde", ["-10.0", "54.0"])
    def test_los_bordes_del_rango_valen(self, borde):
        assert StrokePlaySetup.create(category_limits=_d(borde)).category_limits == (
            Decimal(borde),
        )

    def test_con_dos_decimales_se_rechaza(self):
        with pytest.raises(StrokePlaySettingsError, match="un decimal"):
            StrokePlaySetup.create(category_limits=_d("12.05"))

    def test_un_limite_negativo_vale(self):
        """Un plus es un hándicap como otro: «hasta +2,0» es una categoría posible."""
        assert StrokePlaySetup.create(category_limits=_d("-2.0")).number_of_categories == 2


class TestJornadasPorJugador:
    @pytest.mark.parametrize("jornadas", [0, -1])
    def test_menos_de_una_se_rechaza(self, jornadas):
        with pytest.raises(StrokePlaySettingsError, match="al menos una jornada"):
            StrokePlaySetup.create(max_matchdays_per_player=jornadas)

    def test_no_puede_pasar_de_los_dias_del_torneo(self):
        ajustes = StrokePlaySetup.create(max_matchdays_per_player=3)

        with pytest.raises(StrokePlaySettingsError, match="3 jornadas.*2 días"):
            ajustes.check_fits_in(days=2)

    def test_tantas_como_dias_vale(self):
        StrokePlaySetup.create(max_matchdays_per_player=2).check_fits_in(days=2)


class TestCambiar:
    def test_cambiar_un_ajuste_deja_los_otros_como_estaban(self):
        antes = StrokePlaySetup.create(
            category_limits=_d("12.0"),
            max_matchdays_per_player=2,
            overall_standing=OverallStanding.BEST_CARD,
        )

        despues = antes.with_changes(max_matchdays_per_player=1)

        assert despues.category_limits == (Decimal("12.0"),)
        assert despues.max_matchdays_per_player == 1
        assert despues.overall_standing is OverallStanding.BEST_CARD

    def test_una_lista_vacia_quita_las_categorias(self):
        antes = StrokePlaySetup.create(category_limits=_d("12.0", "26.0"))

        assert antes.with_changes(category_limits=[]).category_limits == ()

    def test_un_cambio_se_valida_igual_que_al_crear(self):
        with pytest.raises(StrokePlaySettingsError):
            StrokePlaySetup.create().with_changes(category_limits=_d("26.0", "12.0"))

    def test_es_inmutable(self):
        """Se guarda con `composite()`: un cambio por dentro se perdería sin avisar."""
        ajustes = StrokePlaySetup.create()

        with pytest.raises(AttributeError):
            ajustes.max_matchdays_per_player = 2  # type: ignore[misc]


class TestGuardarYLeer:
    def test_ida_y_vuelta_por_las_columnas(self):
        ajustes = StrokePlaySetup.create(
            category_limits=_d("12.0", "26.0"),
            max_matchdays_per_player=2,
            overall_standing=OverallStanding.BEST_CARD,
        )

        assert StrokePlaySetup.from_columns(*ajustes.__composite_values__()) == ajustes

    def test_sin_jornadas_guardadas_no_es_un_stroke_play(self):
        """Una Ryder deja las tres columnas vacías."""
        assert StrokePlaySetup.from_columns(None, None, None) is None


class TestUnDecimalSiempre:
    def test_un_limite_entero_se_guarda_con_su_decimal(self):
        """Si no, responde «12» al cambiarlo y «12.0» al leerlo de la base de datos."""
        ajustes = StrokePlaySetup.create(category_limits=[Decimal("12"), Decimal("26")])

        assert [str(v) for v in ajustes.category_limits] == ["12.0", "26.0"]

    def test_al_cambiar_tambien(self):
        ajustes = StrokePlaySetup.create().with_changes(category_limits=[Decimal("18")])

        assert [str(v) for v in ajustes.category_limits] == ["18.0"]


class TestNumerosImposibles:
    """Lo que no es un hándicap se rechaza con su motivo, nunca con un 500 (CodeRabbit, #501)."""

    @pytest.mark.parametrize("enorme", ["1E+50", "-1E+50", "1E+30"])
    def test_un_limite_desmesurado_se_rechaza_por_el_rango(self, enorme):
        with pytest.raises(StrokePlaySettingsError, match="entre -10,0 y 54,0"):
            StrokePlaySetup.create(category_limits=[Decimal(enorme)])

    @pytest.mark.parametrize("raro", ["NaN", "Infinity", "-Infinity"])
    def test_lo_que_no_es_un_numero_tambien(self, raro):
        with pytest.raises(StrokePlaySettingsError, match="entre -10,0 y 54,0"):
            StrokePlaySetup.create(category_limits=[Decimal(raro)])
