"""
La hoja de salidas de una franja de stroke play (#251, decidido el 6-7 oct 2026).

Primera salida, ÚLTIMA salida (la hora final es la última salida posible),
intervalo y tamaño de partida. De ahí salen las horas y el cupo.

| Caso                                   | Resultado                          |
|----------------------------------------|------------------------------------|
| 15:00-18:00 cada 10 min, de 4          | 19 salidas, cupo 76                |
| 9:00-9:00                              | Una sola salida                    |
| 9:00-9:25 cada 10 (no cae justa)       | 9:00, 9:10, 9:20                   |
| Última antes que la primera            | Error                              |
| Intervalo 4 o 21                       | Error; 5 y 20 valen                |
| Partida de 2 o 5                       | Error; 3 y 4 valen                 |
| Se solapan (comparten alguna hora)     | Sí, también si se tocan            |
| Una acaba antes de que empiece la otra | No                                 |
"""

from datetime import time

import pytest

from src.modules.competition.domain.value_objects.hoja_de_salidas import (
    HojaDeSalidas,
    HojaDeSalidasInvalidaError,
)


def _hoja(primera="15:00", ultima="18:00", intervalo=10, partida=4) -> HojaDeSalidas:
    return HojaDeSalidas(
        primera_salida=time.fromisoformat(primera),
        ultima_salida=time.fromisoformat(ultima),
        intervalo_minutos=intervalo,
        jugadores_por_partida=partida,
    )


class TestSalidasYCupo:
    def test_la_hora_final_es_la_ultima_salida(self):
        hoja = _hoja()

        assert hoja.numero_de_salidas == 19
        assert hoja.cupo == 76
        assert hoja.salidas[0] == time(15, 0)
        assert hoja.salidas[-1] == time(18, 0)

    def test_una_sola_salida(self):
        hoja = _hoja("09:00", "09:00", partida=3)

        assert hoja.salidas == [time(9, 0)]
        assert hoja.cupo == 3

    def test_si_no_cae_justa_la_ultima_es_la_que_cabe(self):
        assert _hoja("09:00", "09:25").salidas == [time(9, 0), time(9, 10), time(9, 20)]


class TestLoQueNoVale:
    def test_la_ultima_antes_que_la_primera(self):
        with pytest.raises(HojaDeSalidasInvalidaError, match="última salida"):
            _hoja("12:00", "11:50")

    @pytest.mark.parametrize("intervalo", [4, 21, 0])
    def test_intervalo_fuera_de_5_a_20(self, intervalo):
        with pytest.raises(HojaDeSalidasInvalidaError, match="5 y 20"):
            _hoja(intervalo=intervalo)

    @pytest.mark.parametrize("intervalo", [5, 20])
    def test_los_extremos_del_intervalo_valen(self, intervalo):
        assert _hoja(intervalo=intervalo).intervalo_minutos == intervalo

    @pytest.mark.parametrize("partida", [2, 5])
    def test_partida_de_3_o_4(self, partida):
        with pytest.raises(HojaDeSalidasInvalidaError, match="3 o 4"):
            _hoja(partida=partida)


class TestSolape:
    def test_se_solapan_si_comparten_alguna_hora(self):
        assert _hoja("09:00", "12:00").se_solapa_con(_hoja("11:00", "14:00"))

    def test_tambien_si_se_tocan(self):
        assert _hoja("09:00", "12:00").se_solapa_con(_hoja("12:00", "14:00"))

    def test_una_dentro_de_otra(self):
        assert _hoja("09:00", "15:00").se_solapa_con(_hoja("10:00", "11:00"))

    def test_no_si_una_acaba_antes(self):
        assert not _hoja("09:00", "12:00").se_solapa_con(_hoja("12:10", "14:00"))
        assert not _hoja("12:10", "14:00").se_solapa_con(_hoja("09:00", "12:00"))
