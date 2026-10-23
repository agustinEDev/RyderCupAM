"""
Tests del adaptador de partida rapida (BE-2): al cerrarla publica los logros y
como acabo cada uno, y un fallo en uno no se lleva el otro (G27).
"""

import pytest

from src.modules.social.infrastructure.adapters.quick_match_achievements_publisher import (
    QuickMatchAchievementsPublisher,
)

pytestmark = pytest.mark.asyncio


class _Fallo:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("caido")


class _Cuenta:
    def __init__(self, cuantos):
        self.cuantos = cuantos
        self.llamadas: list = []

    async def execute(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))
        return self.cuantos


class TestPartidaRapida:
    async def test_publica_los_logros_y_el_resultado(self):
        logros, resultado = _Cuenta(2), _Cuenta(3)
        adaptador = QuickMatchAchievementsPublisher(logros, resultado)

        assert await adaptador.publish("qm-1") == 5
        # El record se mide al publicar, con las vueltas fechadas: ya no se
        # captura nada antes de cerrar (23 oct 2026)
        assert logros.llamadas == [(("qm-1",), {})]
        assert resultado.llamadas == [(("qm-1",), {})]

    async def test_g27_si_fallan_los_logros_el_resultado_sale_igual(self):
        resultado = _Cuenta(1)
        adaptador = QuickMatchAchievementsPublisher(_Fallo(), resultado)

        assert await adaptador.publish("qm-1") == 1

    async def test_g27_si_falla_el_resultado_los_logros_quedan(self):
        adaptador = QuickMatchAchievementsPublisher(_Cuenta(2), _Fallo())

        assert await adaptador.publish("qm-1") == 2
