"""
Los diferenciales con fecha con los que se mide el record: si las estadisticas
fallan, no hay record, pero el resto de logros de la vuelta se publica igual.
"""

import logging
from datetime import date
from decimal import Decimal

import pytest

from src.modules.social.domain.services.personal_best import DatedDifferential
from src.modules.social.infrastructure.adapters.player_differentials_adapter import (
    StatsPlayerDifferentialsAdapter,
)
from src.modules.user.application.dto.player_stats_dto import RoundDifferentialDTO
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

DIEGO = UserId.generate()


class _Estadisticas:
    def __init__(self, rondas=None, error: Exception | None = None):
        self._rondas = rondas or []
        self._error = error

    async def execute_round_differentials(self, user_id):
        if self._error is not None:
            raise self._error
        return self._rondas


async def test_it_passes_on_each_round_with_its_day_and_origin():
    ronda = RoundDifferentialDTO(
        played_on=date(2026, 10, 12),
        differential=Decimal("36.0"),
        source_id="partida",
        competition_id="torneo",
    )

    rondas = await StatsPlayerDifferentialsAdapter(_Estadisticas([ronda])).round_differentials(
        DIEGO
    )

    assert rondas == [DatedDifferential(date(2026, 10, 12), Decimal("36.0"), "partida", "torneo")]


async def test_if_the_stats_fail_there_are_no_rounds_and_it_is_logged(caplog):
    """Sin vueltas no hay record: lo demas de la vuelta no se pierde por esto."""
    adaptador = StatsPlayerDifferentialsAdapter(_Estadisticas(error=RuntimeError("tee roto")))

    with caplog.at_level(logging.WARNING):
        rondas = await adaptador.round_differentials(DIEGO)

    assert rondas == []
    assert "differentials" in caplog.text
