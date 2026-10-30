"""
Deshacer los equipos a mano (decidido el 30 oct 2026, tabla aprobada).

Con los equipos formados no se invita ni se vuelven a formar: para que entre
alguien nuevo, el organizador los deshace antes. Es el mismo reinicio que al
quitar a un jugador (`TeamAssignmentWriter.deshacer`).

| #  | Quién y cuándo                              | Queda                                   |
|----|---------------------------------------------|-----------------------------------------|
| U1 | Organizador o admin, sin partidos           | Sin equipos, sala, sobres ni subcapitanes; capitanes, sí |
| U2 | Con partidos, o la competición ya empezada  | TEAMS_LOCKED, sin tocar nada            |
| U3 | Sin equipos formados                        | NO_TEAMS                                |
| U4 | Otro jugador / competición que no existe    | No es el creador / no encontrada        |
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.undo_teams_use_case import (
    NoTeamsError,
    TeamsLockedError,
    UndoTeamsUseCase,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import (
    _deshace,
    _jugador,
    _montar,
)

pytestmark = pytest.mark.asyncio


async def _organizador(uow, comp_id) -> UserId:
    async with uow:
        return (await uow.competitions.find_by_id(comp_id)).creator_id


async def _equipos(uow, comp_id):
    async with uow:
        return await uow.team_assignments.find_by_competition(comp_id)


async def test_u1_el_organizador_los_deshace():
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()

    await UndoTeamsUseCase(uow).execute(comp_id.value, await _organizador(uow, comp_id))

    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        assert await uow.team_assignments.find_by_competition(comp_id) is None
        assert await uow.drafts.find_by_competition(comp_id) is None
        assert await uow.envelopes.find_by_round(round_id) == []
    assert competicion.ryder_cup.team_a_vice_captain_id is None
    assert competicion.ryder_cup.team_a_captain_id == equipo_a[0]
    assert competicion.ryder_cup.team_b_captain_id == equipo_b[0]


async def test_u1_un_admin_tambien():
    uow, comp_id, *_ = await _montar()

    await UndoTeamsUseCase(uow).execute(comp_id.value, UserId(uuid4()), is_admin=True)

    assert await _equipos(uow, comp_id) is None


async def test_u2_con_partidos_no():
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    async with uow:
        await uow.matches.add(
            Match.create(
                round_id=round_id,
                match_number=1,
                team_a_players=[_jugador(equipo_a[1])],
                team_b_players=[_jugador(equipo_b[1])],
            )
        )
        await uow.commit()

    with pytest.raises(TeamsLockedError) as error:
        await UndoTeamsUseCase(uow).execute(comp_id.value, await _organizador(uow, comp_id))

    assert error.value.error_code == "TEAMS_LOCKED"
    assert await _equipos(uow, comp_id) is not None


async def test_u2_empezada_no():
    uow, comp_id, *_ = await _montar()
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.start()
        await uow.competitions.update(competicion)
        await uow.commit()

    with pytest.raises(TeamsLockedError):
        await UndoTeamsUseCase(uow).execute(comp_id.value, await _organizador(uow, comp_id))

    assert await _equipos(uow, comp_id) is not None


async def test_u3_sin_equipos():
    uow, comp_id, *_ = await _montar()
    await _deshace(uow, comp_id)

    with pytest.raises(NoTeamsError) as error:
        await UndoTeamsUseCase(uow).execute(comp_id.value, await _organizador(uow, comp_id))

    assert error.value.error_code == "NO_TEAMS"


async def test_u4_otro_no():
    uow, comp_id, _, _, equipo_b = await _montar()

    with pytest.raises(NotCompetitionCreatorError):
        await UndoTeamsUseCase(uow).execute(comp_id.value, equipo_b[1])

    assert await _equipos(uow, comp_id) is not None


async def test_u4_no_existe():
    uow, *_ = await _montar()

    with pytest.raises(CompetitionNotFoundError):
        await UndoTeamsUseCase(uow).execute(CompetitionId(uuid4()).value, UserId(uuid4()))
