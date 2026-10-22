"""El adaptador de logros de torneo: cerrar publica lo propio y luego los del mismo dia."""

import pytest

from src.modules.social.infrastructure.adapters.tournament_achievements_publisher import (
    TournamentAchievementsPublisher,
)

pytestmark = pytest.mark.asyncio


class _Publicar:
    def __init__(self, rompe: bool = False):
        self.llamadas: list[tuple[str, str]] = []
        self._rompe = rompe

    async def execute(self, competition_id: str) -> int:
        self.llamadas.append(("execute", competition_id))
        return 3

    async def republish_same_day(self, competition_id: str) -> int:
        self.llamadas.append(("republish_same_day", competition_id))
        if self._rompe:
            raise RuntimeError("feed caido")
        return 1


async def test_closing_publishes_its_own_and_then_the_same_day_ones():
    publicar = _Publicar()

    assert await TournamentAchievementsPublisher(publicar).publish("t1") == 3  # type: ignore[arg-type]
    assert publicar.llamadas == [("execute", "t1"), ("republish_same_day", "t1")]


async def test_a_failing_republication_keeps_what_was_published():
    publicar = _Publicar(rompe=True)

    assert await TournamentAchievementsPublisher(publicar).publish("t1") == 3  # type: ignore[arg-type]
