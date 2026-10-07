"""
La generación de partidos no lanza dos consultas a la vez sobre la misma sesión (#502).

Pedía los jugadores con `asyncio.gather` sobre una sola AsyncSession, y
SQLAlchemy no admite dos operaciones a la vez en una sesión. Era el gemelo de
lo que se arregló en la reasignación.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class _UnaALaVez:
    def __init__(self):
        self.en_vuelo = 0
        self.maximo = 0

    async def find_by_id(self, user_id):
        self.en_vuelo += 1
        self.maximo = max(self.maximo, self.en_vuelo)
        await asyncio.sleep(0)
        self.en_vuelo -= 1
        usuario = MagicMock()
        usuario.id = user_id
        usuario.handicap = None
        usuario.gender = None
        return usuario


async def test_los_jugadores_se_piden_de_uno_en_uno():
    repo = _UnaALaVez()
    caso = GenerateMatchesUseCase(
        uow=MagicMock(), golf_course_repository=MagicMock(), user_repository=repo
    )
    asignacion = MagicMock()
    asignacion.team_a_player_ids = [UserId.generate() for _ in range(3)]
    asignacion.team_b_player_ids = [UserId.generate() for _ in range(3)]

    await caso._build_handicap_data(
        golf_course=_campo(),
        is_scratch=False,
        team_assignment=asignacion,
        enrollment_map={},
        refrescar_handicap_rfeg=False,
    )

    assert repo.maximo <= 1


def _campo():
    """El mismo campo de mentira que usan los tests de la generación de partidos."""
    from decimal import Decimal

    from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
    from src.shared.domain.value_objects.gender import Gender

    tee = MagicMock()
    tee.color = TeeColor.YELLOW
    tee.gender = Gender.MALE
    tee.course_rating = Decimal("71.2")
    tee.slope_rating = 128
    hoyos = []
    for numero in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = numero
        hoyo.par = 4
        hoyo.stroke_index = numero
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = [tee]
    campo.reference_card = hoyos
    return campo
