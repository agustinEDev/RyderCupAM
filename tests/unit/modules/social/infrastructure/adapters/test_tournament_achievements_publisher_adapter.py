"""El adaptador de logros de torneo: cerrar publica lo propio, y nada mas (22 oct 2026)."""

import pytest

from src.modules.social.infrastructure.adapters.tournament_achievements_publisher import (
    TournamentAchievementsPublisher,
)

pytestmark = pytest.mark.asyncio


class _Publicar:
    def __init__(self):
        self.llamadas: list[tuple[str, str]] = []

    async def execute(self, competition_id: str) -> int:
        self.llamadas.append(("execute", competition_id))
        return 3


async def test_closing_publishes_its_own_only():
    """Los logros exclusivos se mueven solos al publicar: no hay vecinos que republicar."""
    publicar = _Publicar()

    assert await TournamentAchievementsPublisher(publicar).publish("t1") == 3  # type: ignore[arg-type]
    assert publicar.llamadas == [("execute", "t1")]
