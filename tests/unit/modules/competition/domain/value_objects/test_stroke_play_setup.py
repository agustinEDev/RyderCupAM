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
from src.modules.user.domain.value_objects.user_id import UserId


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


class TestCategoriaDeUnHandicap:
    """«Hasta 12,0» incluye el 12,0 (1c)."""

    @pytest.mark.parametrize(
        "handicap, categoria",
        [("12.0", 1), ("12.1", 2), ("26.0", 2), ("26.1", 3), ("-2.0", 1), ("54.0", 3)],
    )
    def test_con_limites_de_12_y_26(self, handicap, categoria):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0", "26.0"))

        assert ajustes.category_for(Decimal(handicap)) == categoria

    def test_sin_limites_todos_en_la_primera(self):
        assert StrokePlaySetup.create().category_for(Decimal("30.0")) == 1

    def test_sin_handicap_no_hay_categoria(self):
        assert StrokePlaySetup.create(category_limits=_d("12.0")).category_for(None) is None


class TestSeisPorCategoria:
    """Una categoría con menos de 6 se une a la contigua de hándicap más bajo (7 oct)."""

    @staticmethod
    def _jugadores(*handicaps: str) -> dict:
        from src.modules.user.domain.value_objects.user_id import UserId

        return {UserId.generate(): (Decimal(h) if h is not None else None) for h in handicaps}

    def test_con_seis_en_cada_una_se_quedan_como_estan(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))
        jugadores = self._jugadores(*(["5.0"] * 6 + ["20.0"] * 6))

        categorias = ajustes.categorias(jugadores)

        assert sorted(set(categorias.values())) == [1, 2]

    def test_la_ultima_con_menos_de_seis_se_une_a_la_anterior(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0", "26.0"))
        jugadores = self._jugadores(*(["5.0"] * 6 + ["20.0"] * 6 + ["30.0"] * 5))

        categorias = ajustes.categorias(jugadores)

        assert sorted(set(categorias.values())) == [1, 2]
        tercera = [u for u, h in jugadores.items() if h == Decimal("30.0")]
        assert {categorias[u] for u in tercera} == {2}

    def test_la_primera_con_menos_de_seis_se_une_a_la_segunda(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))
        jugadores = self._jugadores(*(["5.0"] * 3 + ["20.0"] * 6))

        assert set(ajustes.categorias(jugadores).values()) == {1}

    def test_en_cascada_hasta_que_todas_tengan_seis(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("5.0", "12.0", "20.0"))
        jugadores = self._jugadores(*(["3.0"] * 6 + ["8.0"] * 2 + ["15.0"] * 2 + ["25.0"] * 2))

        categorias = ajustes.categorias(jugadores)

        # 8, 15 y 25 (2 cada una) se van juntando hasta tener 6: dos categorías
        assert sorted(set(categorias.values())) == [1, 2]

    def test_con_menos_de_seis_en_total_una_sola(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))
        jugadores = self._jugadores("5.0", "20.0")

        assert set(ajustes.categorias(jugadores).values()) == {1}

    def test_quien_no_tiene_handicap_no_tiene_categoria_ni_cuenta(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))
        jugadores = self._jugadores(*(["5.0"] * 6 + ["20.0"] * 6), None)
        sin = next(u for u, h in jugadores.items() if h is None)

        categorias = ajustes.categorias(jugadores)

        assert categorias[sin] is None
        assert sorted({c for c in categorias.values() if c}) == [1, 2]

    def test_una_del_medio_se_une_a_la_de_handicap_mas_bajo_y_no_a_la_otra(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("5.0", "12.0"))
        jugadores = self._jugadores(*(["3.0"] * 6 + ["8.0"] * 3 + ["20.0"] * 6))

        categorias = ajustes.categorias(jugadores)

        segunda = {categorias[u] for u, h in jugadores.items() if h == Decimal("8.0")}
        primera = {categorias[u] for u, h in jugadores.items() if h == Decimal("3.0")}
        tercera = {categorias[u] for u, h in jugadores.items() if h == Decimal("20.0")}
        assert segunda == primera == {1}
        assert tercera == {2}


# ----------------------------------------------------------------------
# Categorías iguales, repartidas al cerrar (decidido con Agustín el 10 oct 2026)
# ----------------------------------------------------------------------


def _hs(*valores: str | float) -> list[Decimal]:
    return [Decimal(str(v)) for v in valores]


def _grupos(ajustes: StrokePlaySetup, handicaps: list[Decimal]) -> list[int]:
    """Cuántos caen en cada categoría nominal (sin la regla de los seis)."""
    por = [0] * ajustes.number_of_categories
    for h in handicaps:
        por[ajustes.category_for(h) - 1] += 1
    return por


class TestCategoriasIgualesAlCrear:
    def test_con_un_contador_se_guarda_y_no_hay_limites_hasta_el_cierre(self):
        ajustes = StrokePlaySetup.create(category_count=3)

        assert ajustes.category_count == 3
        assert ajustes.category_limits == ()

    def test_sin_contador_son_limites_a_mano(self):
        assert StrokePlaySetup.create(category_limits=_d("12.0")).category_count is None

    @pytest.mark.parametrize("contador", [0, 1, 6, -2])
    def test_fuera_de_2_a_5_se_rechaza(self, contador):
        with pytest.raises(StrokePlaySettingsError, match="entre 2 y 5"):
            StrokePlaySetup.create(category_count=contador)

    @pytest.mark.parametrize("contador", [2, 5])
    def test_los_bordes_valen(self, contador):
        assert StrokePlaySetup.create(category_count=contador).category_count == contador

    @pytest.mark.parametrize("raro", [2.5, True, "3"])
    def test_lo_que_no_es_un_entero_se_rechaza(self, raro):
        with pytest.raises(StrokePlaySettingsError, match="entre 2 y 5"):
            StrokePlaySetup.create(category_count=raro)

    def test_limites_y_contador_a_la_vez_se_rechazan(self):
        with pytest.raises(StrokePlaySettingsError, match="a la vez"):
            StrokePlaySetup.create(category_limits=_d("12.0"), category_count=3)


class TestCambiarDeModo:
    def test_de_iguales_a_mano_borra_el_contador(self):
        ajustes = StrokePlaySetup.create(category_count=3)

        nuevos = ajustes.with_changes(category_limits=_d("12.0", "26.0"))

        assert nuevos.category_count is None
        assert nuevos.category_limits == (Decimal("12.0"), Decimal("26.0"))

    def test_a_mano_con_lista_vacia_tambien_borra_el_contador(self):
        nuevos = StrokePlaySetup.create(category_count=3).with_changes(category_limits=[])

        assert nuevos.category_count is None
        assert nuevos.number_of_categories == 1

    def test_de_mano_a_iguales_borra_los_limites(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0", "26.0"))

        nuevos = ajustes.with_changes(category_count=4)

        assert nuevos.category_count == 4
        assert nuevos.category_limits == ()

    def test_los_dos_a_la_vez_se_rechazan(self):
        with pytest.raises(StrokePlaySettingsError, match="a la vez"):
            StrokePlaySetup.create().with_changes(category_limits=_d("12.0"), category_count=3)

    def test_cambiar_otra_cosa_no_toca_el_modo(self):
        nuevos = StrokePlaySetup.create(category_count=3).with_changes(max_matchdays_per_player=2)

        assert nuevos.category_count == 3
        assert nuevos.category_limits == ()


class TestRepartir:
    def test_treinta_distintos_en_tres_son_diez_diez_y_diez(self):
        handicaps = _hs(*range(1, 31))
        ajustes = StrokePlaySetup.create(category_count=3).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("10.0"), Decimal("20.0"))
        assert _grupos(ajustes, handicaps) == [10, 10, 10]

    def test_treinta_y_uno_en_tres_son_diez_once_y_diez(self):
        handicaps = _hs(*range(1, 32))
        ajustes = StrokePlaySetup.create(category_count=3).repartir(handicaps)

        assert _grupos(ajustes, handicaps) == [10, 11, 10]

    def test_el_orden_de_llegada_no_importa(self):
        handicaps = _hs(*range(30, 0, -1))
        ajustes = StrokePlaySetup.create(category_count=3).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("10.0"), Decimal("20.0"))

    def test_los_empatados_en_la_frontera_van_todos_a_la_mas_baja(self):
        # 12 jugadores en 2: la frontera cae en el 6.º, que empata con el 7.º y el 8.º
        handicaps = _hs(1, 2, 3, 4, 5, "9.4", "9.4", "9.4", 20, 21, 22, 23)
        ajustes = StrokePlaySetup.create(category_count=2).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("9.4"),)
        assert _grupos(ajustes, handicaps) == [8, 4]

    def test_si_dos_limites_coinciden_salen_menos_categorias(self):
        # 18 en 3: las fronteras (6.º y 12.º) caen las dos en el 15,0
        handicaps = _hs(1, 2, *(["15.0"] * 14), 30, 31)
        ajustes = StrokePlaySetup.create(category_count=3).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("15.0"),)
        assert ajustes.number_of_categories == 2

    def test_si_todos_tienen_el_mismo_sale_una_sola(self):
        ajustes = StrokePlaySetup.create(category_count=3).repartir(_hs(*(["12.0"] * 9)))

        assert ajustes.category_limits == ()

    def test_un_empate_arriba_baja_la_frontera_por_debajo_del_empate(self):
        # 13 en 2: la frontera (7.º) cae en el 10,0 de los siete de arriba; con
        # «empates abajo» la 2.ª quedaría vacía: los empatados suben juntos
        handicaps = _hs(1, 2, 3, 4, 5, 6, *(["10.0"] * 7))
        ajustes = StrokePlaySetup.create(category_count=2).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("6.0"),)
        assert _grupos(ajustes, handicaps) == [6, 7]

    def test_un_empate_en_medio_sigue_yendo_abajo(self):
        handicaps = _hs(1, 2, 3, 4, 5, "9.4", "9.4", 20, 21, 22, 23, 24, 25)
        ajustes = StrokePlaySetup.create(category_count=2).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("9.4"),)

    def test_ninguna_categoria_nace_vacia(self):
        handicaps = _hs(*range(1, 13), *(["30.0"] * 18))
        ajustes = StrokePlaySetup.create(category_count=5).repartir(handicaps)

        assert 0 not in _grupos(ajustes, handicaps)

    def test_sin_inscritos_no_hay_limites(self):
        assert StrokePlaySetup.create(category_count=3).repartir([]).category_limits == ()

    def test_los_plus_van_primero(self):
        handicaps = _hs(8, 7, 6, 5, 4, 3, "0.5", 0, "-0.5", -1, "-1.5", -2)
        ajustes = StrokePlaySetup.create(category_count=2).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("0.5"),)

    def test_quien_no_tiene_handicap_no_cuenta(self):
        handicaps = [*_hs(*range(1, 31)), None]
        ajustes = StrokePlaySetup.create(category_count=3).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("10.0"), Decimal("20.0"))

    def test_conserva_el_contador_y_lo_demas(self):
        ajustes = StrokePlaySetup.create(
            category_count=3, max_matchdays_per_player=2, overall_standing=OverallStanding.BEST_CARD
        ).repartir(_hs(*range(1, 31)))

        assert ajustes.category_count == 3
        assert ajustes.max_matchdays_per_player == 2
        assert ajustes.overall_standing is OverallStanding.BEST_CARD

    def test_a_mano_no_se_reparte(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))

        assert ajustes.repartir(_hs(*range(1, 31))) == ajustes

    def test_repartir_otra_vez_parte_de_cero(self):
        primero = StrokePlaySetup.create(category_count=2).repartir(_hs(*range(1, 31)))

        segundo = primero.repartir(_hs(*range(41, 53)))

        assert segundo.category_limits == (Decimal("46.0"),)

    def test_sin_seis_para_cada_una_se_reparte_en_las_que_caben(self):
        # 14 para 3: con 6 como mínimo caben 2, de 7 (decidido el 10 oct 2026)
        handicaps = _hs(*range(1, 15))
        ajustes = StrokePlaySetup.create(category_count=3).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("7.0"),)
        assert _grupos(ajustes, handicaps) == [7, 7]

    @pytest.mark.parametrize(("jugadores", "categorias"), [(11, 1), (12, 2), (17, 2), (18, 3)])
    def test_caben_tantas_como_grupos_de_seis(self, jugadores, categorias):
        handicaps = _hs(*range(1, jugadores + 1))
        ajustes = StrokePlaySetup.create(category_count=5).repartir(handicaps)

        assert ajustes.number_of_categories == categorias

    def test_y_despues_la_regla_de_los_seis_si_un_empate_deja_una_corta(self):
        # 12 en 2, con el empate abajo: 8 y 4 → la de 4 se une a la 1.ª
        handicaps = _hs(1, 2, 3, 4, 5, "9.4", "9.4", "9.4", 20, 21, 22, 23)
        ajustes = StrokePlaySetup.create(category_count=2).repartir(handicaps)
        categorias = ajustes.categorias({UserId.generate(): h for h in handicaps})

        assert set(categorias.values()) == {1}

    def test_un_solo_jugador_no_da_para_limites(self):
        assert StrokePlaySetup.create(category_count=3).repartir(_hs(7)).category_limits == ()

    def test_dos_jugadores_en_dos_es_una_sola(self):
        assert StrokePlaySetup.create(category_count=2).repartir(_hs(7, 9)).category_limits == ()


class TestElRedondeoViveEnElDominio:
    """Lo que se compara es lo que se guarda: un decimal (revisión del 10 oct 2026)."""

    def test_repartir_con_centesimos_no_rompe_y_da_un_decimal(self):
        handicaps = _hs(1, 2, 3, 4, 5, "6.05", 20, 21, 22, 23, 24, 25)

        ajustes = StrokePlaySetup.create(category_count=2).repartir(handicaps)

        assert ajustes.category_limits == (Decimal("6.1"),)

    def test_la_categoria_sale_del_handicap_redondeado(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))

        assert ajustes.category_for(Decimal("12.04")) == 1
        assert ajustes.category_for(Decimal("12.05")) == 2


class TestQuitarElReparto:
    def test_en_iguales_borra_los_limites_calculados(self):
        repartido = StrokePlaySetup.create(category_count=3).repartir(_hs(*range(1, 31)))

        limpio = repartido.sin_reparto()

        assert limpio.category_limits == ()
        assert limpio.category_count == 3

    def test_a_mano_no_toca_nada(self):
        ajustes = StrokePlaySetup.create(category_limits=_d("12.0"))

        assert ajustes.sin_reparto() == ajustes


class TestGuardarElContador:
    def test_ida_y_vuelta_por_las_columnas(self):
        ajustes = StrokePlaySetup.create(category_count=3).repartir(_hs(*range(1, 31)))

        leido = StrokePlaySetup.from_columns(*ajustes.__composite_values__())

        assert leido == ajustes

    def test_una_fila_de_antes_del_contador_es_a_mano(self):
        leido = StrokePlaySetup.from_columns([Decimal("12.0")], 1, "ACCUMULATED", None)

        assert leido.category_count is None
