"""
Tests de los puestos con empates (BE-2, casos 17 y 31) y del desempate por
hándicap (tabla del 22 oct 2026, H).

| Caso                                              | Resultado                         |
|---------------------------------------------------|-----------------------------------|
| Mismo valor, distinto hándicap                    | Delante el de menos hándicap      |
| Mismo valor y el mismo hándicap exacto            | Comparten puesto (tied)           |
| Empate triple con hándicaps mezclados             | 1.º el menor; los dos iguales, T2 |
| Sin hándicap en el empate (cuenta como 0)         | Delante de 30.0; T con un 0.0     |
| Dos sin hándicap en el empate                     | Comparten puesto (los dos, 0)     |
| Plus (negativo) contra 0                          | Delante el plus                   |
| 12.4 contra 12.40 (float y Decimal)               | El mismo hándicap: comparten      |
"""

from decimal import Decimal

import pytest

from src.modules.social.domain.services.ranking import Puesto, rank

SIN = None


class TestPuestos:
    def test_mas_es_mejor_ordena_de_mayor_a_menor(self):
        """Given puntos Stableford / When se ordenan / Then el de mas puntos, primero."""
        assert rank([30, 36, 33], [10.0, 10.0, 10.0], higher_is_better=True) == [
            Puesto(3, False),
            Puesto(1, False),
            Puesto(2, False),
        ]

    def test_menos_es_mejor_ordena_de_menor_a_mayor(self):
        """Given golpes respecto al par (Medal) / When se ordenan / Then el de menos, primero."""
        assert rank([2, -1, 5], [10.0, 10.0, 10.0], higher_is_better=False) == [
            Puesto(2, False),
            Puesto(1, False),
            Puesto(3, False),
        ]

    def test_31_con_el_mismo_handicap_comparten_puesto_y_el_siguiente_salta(self):
        """
        31 y H3. Given dos empatados arriba con el mismo hándicap / When se
        ordenan / Then los dos 1.º empatados y el siguiente 3.º.
        """
        assert rank([34, 34, 30], [12.4, 12.4, 3.0], higher_is_better=True) == [
            Puesto(1, True),
            Puesto(1, True),
            Puesto(3, False),
        ]

    def test_empate_en_medio_con_el_mismo_handicap(self):
        assert rank([36, 30, 30, 20], [5.0, 8.0, 8.0, 1.0], higher_is_better=True) == [
            Puesto(1, False),
            Puesto(2, True),
            Puesto(2, True),
            Puesto(4, False),
        ]

    @pytest.mark.parametrize("valores", [[], [7]])
    def test_vacio_o_uno_solo(self, valores):
        handicaps = [10.0 for _ in valores]
        assert rank(valores, handicaps, higher_is_better=True) == [
            Puesto(1, False) for _ in valores
        ]


class TestDesempatePorHandicap:
    def test_h1_a_igual_valor_delante_el_de_menos_handicap(self):
        """H1. Given 36 y 36 con 18.0 y 12.4 / Then el de 12.4 1.º y el otro 2.º, sin empate."""
        assert rank([36, 36], [18.0, 12.4], higher_is_better=True) == [
            Puesto(2, False),
            Puesto(1, False),
        ]

    def test_h1_tambien_en_medal(self):
        """H1. Given +2 y +2 netos / Then delante el de menos hándicap."""
        assert rank([2, 2, 1], [3.1, 3.0, 20.0], higher_is_better=False) == [
            Puesto(3, False),
            Puesto(2, False),
            Puesto(1, False),
        ]

    def test_h2_el_indice_exacto_decide_por_una_decima(self):
        """H2. Given 12.4 y 12.5 / Then decide la décima."""
        assert rank([30, 30], [12.5, 12.4], higher_is_better=True) == [
            Puesto(2, False),
            Puesto(1, False),
        ]

    def test_empate_triple_con_handicaps_mezclados(self):
        """Given tres a 30 con 12.4, 8.1 y 12.4, y uno a 25 / Then 8.1 1.º, los 12.4 T2, 4.º."""
        assert rank([30, 30, 30, 25], [12.4, 8.1, 12.4, 0.0], higher_is_better=True) == [
            Puesto(2, True),
            Puesto(1, False),
            Puesto(2, True),
            Puesto(4, False),
        ]

    def test_h4_sin_handicap_cuenta_como_cero(self):
        """H4 (22 oct 2026). Given 36 sin hándicap y 36 con 30.0 / Then el sin hándicap delante."""
        assert rank([36, 36], [SIN, 30.0], higher_is_better=True) == [
            Puesto(1, False),
            Puesto(2, False),
        ]

    def test_h4_sin_handicap_empata_con_un_cero(self):
        assert rank([36, 36], [SIN, 0.0], higher_is_better=True) == [
            Puesto(1, True),
            Puesto(1, True),
        ]

    def test_h4_sin_handicap_queda_detras_de_un_plus(self):
        assert rank([36, 36], [SIN, -0.1], higher_is_better=True) == [
            Puesto(2, False),
            Puesto(1, False),
        ]

    def test_h4_sin_handicap_no_cambia_lo_que_no_esta_empatado(self):
        """Given 37 sin hándicap y 36 con 1.0 / Then el de 37, primero."""
        assert rank([37, 36], [SIN, 1.0], higher_is_better=True) == [
            Puesto(1, False),
            Puesto(2, False),
        ]

    def test_dos_sin_handicap_comparten_puesto(self):
        """Dos sin hándicap empatados a valor tienen el mismo: 0."""
        assert rank([36, 36, 36], [SIN, SIN, 5.0], higher_is_better=True) == [
            Puesto(1, True),
            Puesto(1, True),
            Puesto(3, False),
        ]

    def test_un_plus_va_delante_de_un_cero(self):
        """Given un +1 (-1.0) y un 0.0 empatados / Then el plus delante: tiene menos."""
        assert rank([30, 30], [0.0, -1.0], higher_is_better=True) == [
            Puesto(2, False),
            Puesto(1, False),
        ]

    def test_el_mismo_handicap_escrito_distinto_es_el_mismo(self):
        """Given 12.4 (float) y Decimal('12.40') / Then es el mismo hándicap: comparten."""
        assert rank([30, 30], [12.4, Decimal("12.40")], higher_is_better=True) == [
            Puesto(1, True),
            Puesto(1, True),
        ]
