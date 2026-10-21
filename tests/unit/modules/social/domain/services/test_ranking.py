"""Tests de los puestos con empates (BE-2, casos 17 y 31)."""

import pytest

from src.modules.social.domain.services.ranking import Puesto, rank


class TestPuestos:
    def test_mas_es_mejor_ordena_de_mayor_a_menor(self):
        """Given puntos Stableford / When se ordenan / Then el de mas puntos, primero."""
        assert rank([30, 36, 33], higher_is_better=True) == [
            Puesto(3, False),
            Puesto(1, False),
            Puesto(2, False),
        ]

    def test_menos_es_mejor_ordena_de_menor_a_mayor(self):
        """Given golpes respecto al par (Medal) / When se ordenan / Then el de menos, primero."""
        assert rank([2, -1, 5], higher_is_better=False) == [
            Puesto(2, False),
            Puesto(1, False),
            Puesto(3, False),
        ]

    def test_31_los_empatados_comparten_puesto_y_el_siguiente_salta(self):
        """
        31. Given dos empatados arriba / When se ordenan / Then los dos 1.º
        empatados y el siguiente 3.º, como en cualquier clasificacion de golf.
        """
        assert rank([34, 34, 30], higher_is_better=True) == [
            Puesto(1, True),
            Puesto(1, True),
            Puesto(3, False),
        ]

    def test_empate_en_medio(self):
        assert rank([36, 30, 30, 20], higher_is_better=True) == [
            Puesto(1, False),
            Puesto(2, True),
            Puesto(2, True),
            Puesto(4, False),
        ]

    @pytest.mark.parametrize("valores", [[], [7]])
    def test_vacio_o_uno_solo(self, valores):
        assert rank(valores, higher_is_better=True) == [Puesto(1, False) for _ in valores]
