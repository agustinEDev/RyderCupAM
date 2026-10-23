"""
El adaptador lleva a Actividad la clasificacion final de una Ryder (tabla del
22 oct 2026, I): los puntos salen del leaderboard oficial, sin recalcularlos, y
los equipos de la asignacion de equipos mas quien jugo algun partido.
"""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    RyderResultRef,
)
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class _Avisos:
    def __init__(self):
        self.llamadas: list[tuple] = []

    def __getattr__(self, nombre):
        async def _apunta(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))

        return _apunta


class _General:
    def __init__(self):
        self.pedida: list = []

    async def execute(self, competition_id, categoria=None):
        self.pedida.append(competition_id)
        return SimpleNamespace(tournament_type="STABLEFORD", rows=[])


class _Marcador:
    """El leaderboard oficial de la Ryder: lo que devuelve, tal cual."""

    def __init__(self, a: float, b: float, partidos=()):
        self.pedido: list = []
        self._respuesta = SimpleNamespace(
            team_a_name="Europa",
            team_b_name="USA",
            team_a_points=a,
            team_b_points=b,
            matches=list(partidos),
        )

    async def execute(self, competition_id_str):
        self.pedido.append(competition_id_str)
        return self._respuesta


def _partido(equipo_a, equipo_b):
    return SimpleNamespace(
        team_a_players=[SimpleNamespace(user_id=str(u)) for u in equipo_a],
        team_b_players=[SimpleNamespace(user_id=str(u)) for u in equipo_b],
    )


def _ryder():
    return SimpleNamespace(
        id=CompetitionId(uuid4()),
        name="Ryder de Otoño",
        dates=SimpleNamespace(start_date=date(2027, 3, 3), end_date=date(2027, 3, 5)),
        visibility=Visibility.PRIVATE,
        stroke_play=None,
    )


async def _equipos(uow, competicion, a, b):
    async with uow:
        await uow.team_assignments.add(
            TeamAssignment.create(competicion.id, TeamAssignmentMode.MANUAL, list(a), list(b))
        )


async def test_i8_los_puntos_del_leaderboard_y_los_equipos_de_la_asignacion():
    avisos, uow = _Avisos(), InMemoryUnitOfWork()
    competicion = _ryder()
    ana, eva, luz, mar = (UserId.generate() for _ in range(4))
    await _equipos(uow, competicion, [ana, eva], [luz, mar])
    marcador = _Marcador(15.5, 12.5, [_partido([ana], [luz])])

    await CompetitionActivityPublisher(
        avisos, _General(), uow, ryder_scoreboard=marcador
    ).completed(competicion)

    assert marcador.pedido == [str(competicion.id.value)]
    ((nombre, (torneo, resultado), _),) = avisos.llamadas
    assert nombre == "ryder_final_result"
    assert torneo.competition_id == str(competicion.id.value)
    assert resultado == RyderResultRef(
        team_a_name="Europa",
        team_b_name="USA",
        team_a_points=15.5,
        team_b_points=12.5,
        team_a=(ana, eva),
        team_b=(luz, mar),
    )


async def test_quien_jugo_un_partido_sin_estar_en_la_asignacion_tambien_cuenta():
    avisos, uow = _Avisos(), InMemoryUnitOfWork()
    competicion = _ryder()
    ana, luz, suplente = (UserId.generate() for _ in range(3))
    await _equipos(uow, competicion, [ana], [luz])
    marcador = _Marcador(1.0, 0.0, [_partido([ana], [luz]), _partido([suplente], [luz])])

    await CompetitionActivityPublisher(
        avisos, _General(), uow, ryder_scoreboard=marcador
    ).completed(competicion)

    resultado = avisos.llamadas[0][1][1]
    assert resultado.team_a == (ana, suplente)
    assert resultado.team_b == (luz,)


async def test_sin_asignacion_los_equipos_salen_de_los_partidos():
    avisos, uow = _Avisos(), InMemoryUnitOfWork()
    competicion = _ryder()
    ana, luz = UserId.generate(), UserId.generate()

    await CompetitionActivityPublisher(
        avisos, _General(), uow, ryder_scoreboard=_Marcador(0.5, 0.5, [_partido([ana], [luz])])
    ).completed(competicion)

    resultado = avisos.llamadas[0][1][1]
    assert (resultado.team_a, resultado.team_b) == ((ana,), (luz,))


async def test_un_stroke_play_no_pide_el_marcador_de_la_ryder():
    avisos, uow = _Avisos(), InMemoryUnitOfWork()
    competicion = _ryder()
    competicion.stroke_play = object()
    marcador = _Marcador(0.0, 0.0)

    await CompetitionActivityPublisher(
        avisos, _General(), uow, ryder_scoreboard=marcador
    ).completed(competicion)

    assert marcador.pedido == []
    assert [nombre for nombre, *_ in avisos.llamadas] == ["final_standings"]
