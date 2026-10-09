"""
Cómo se reparten los jugadores de una franja en partidas (#251, PR 4; D4 y D6 del 9 oct 2026).

Por hándicap fijado, en el orden que elija el organizador; a igual hándicap, sale
antes quien cogió antes la plaza. Partidas del tamaño de la hoja, y si sobrara uno
solo, la penúltima cede uno: nunca una partida de 1 al generar.

| Jugadores / tamaño | Partidas      |
|--------------------|---------------|
| 8 / 4              | 4, 4          |
| 3 / 3              | 3             |
| 2 / 4              | 2             |
| 6 / 4              | 4, 2          |
| 5 / 4              | 3, 2          |
| 9 / 4              | 4, 3, 2       |
| 13 / 4             | 4, 4, 3, 2    |
| 7 / 3              | 3, 2, 2       |
| 4 / 3              | 2, 2          |
| 10 / 3             | 3, 3, 2, 2    |
| 0                  | Ninguna       |
| 1                  | Error         |

| Orden                    | Primera partida                          |
|--------------------------|------------------------------------------|
| Más altos primero        | Los hándicaps más altos                  |
| Más bajos primero        | Los más bajos                            |
| Empate de hándicap       | Quien cogió antes la plaza, en los dos   |
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.modules.competition.domain.services.reparto_de_partidas import (
    ParaRepartir,
    RepartoDePartidas,
    RepartoImposibleError,
)
from src.modules.competition.domain.value_objects.orden_de_salida import OrdenDeSalida
from src.modules.user.domain.value_objects.user_id import UserId

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _jugadores(n: int) -> list[ParaRepartir]:
    """Hándicaps 0, 1, 2…, plazas cogidas en ese mismo orden."""
    return [
        ParaRepartir(
            user_id=UserId.generate(),
            handicap=Decimal(i),
            plaza_cogida=INICIO + timedelta(minutes=i),
        )
        for i in range(n)
    ]


class TestTamanos:
    @pytest.mark.parametrize(
        ("n", "tamano", "esperado"),
        [
            (8, 4, [4, 4]),
            (3, 3, [3]),
            (2, 4, [2]),
            (6, 4, [4, 2]),
            (5, 4, [3, 2]),
            (9, 4, [4, 3, 2]),
            (13, 4, [4, 4, 3, 2]),
            (7, 3, [3, 2, 2]),
            (4, 3, [2, 2]),
            (10, 3, [3, 3, 2, 2]),
            (0, 4, []),
        ],
    )
    def test_sizes(self, n, tamano, esperado):
        partidas = RepartoDePartidas.repartir(_jugadores(n), tamano, OrdenDeSalida.HIGH_FIRST)

        assert [len(p) for p in partidas] == esperado

    def test_everybody_plays_once(self):
        jugadores = _jugadores(13)

        partidas = RepartoDePartidas.repartir(jugadores, 4, OrdenDeSalida.HIGH_FIRST)

        repartidos = [u for p in partidas for u in p]
        assert sorted(map(str, repartidos)) == sorted(str(j.user_id) for j in jugadores)

    def test_one_player_alone_is_refused(self):
        with pytest.raises(RepartoImposibleError):
            RepartoDePartidas.repartir(_jugadores(1), 4, OrdenDeSalida.HIGH_FIRST)


class TestOrden:
    def test_high_first_sends_the_highest_handicaps_out_first(self):
        jugadores = _jugadores(8)

        partidas = RepartoDePartidas.repartir(jugadores, 4, OrdenDeSalida.HIGH_FIRST)

        assert partidas[0] == [j.user_id for j in reversed(jugadores[4:])]
        assert partidas[1] == [j.user_id for j in reversed(jugadores[:4])]

    def test_low_first_sends_the_lowest_handicaps_out_first(self):
        jugadores = _jugadores(8)

        partidas = RepartoDePartidas.repartir(jugadores, 4, OrdenDeSalida.LOW_FIRST)

        assert partidas[0] == [j.user_id for j in jugadores[:4]]
        assert partidas[1] == [j.user_id for j in jugadores[4:]]

    @pytest.mark.parametrize("orden", list(OrdenDeSalida))
    def test_a_tie_goes_to_whoever_took_the_place_first(self, orden):
        """Mismo hándicap: la plaza más antigua va antes, se ordene como se ordene."""
        temprano, tarde = UserId.generate(), UserId.generate()
        jugadores = [
            ParaRepartir(tarde, Decimal("10.0"), INICIO + timedelta(hours=1)),
            ParaRepartir(temprano, Decimal("10.0"), INICIO),
        ]

        partidas = RepartoDePartidas.repartir(jugadores, 4, orden)

        assert partidas == [[temprano, tarde]]
