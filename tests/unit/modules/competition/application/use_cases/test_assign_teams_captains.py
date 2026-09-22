"""
El reparto de equipos respeta a los capitanes (BE #320).

Hasta ahora nada garantizaba que un capitán acabara en el equipo que capitanea:
no existía la figura. Decidido el 20 sep: nombrarlos fija a cada uno en su
equipo, y no entran en el draft, que reparte al resto.

Sin capitanes, el reparto sigue como siempre: es el flujo viejo, que convive
con el nuevo durante la transición. Con uno solo —el otro se dio de baja— no se
reparte cojo: se pide nombrar al que falta.
"""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import AssignTeamsRequestDTO
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
)
from src.modules.competition.domain.entities.competition import (
    CaptainMissingError,
    CaptainOnWrongTeamError,
)
from src.modules.competition.domain.services.snake_draft_service import (
    PlayerForDraft,
    SnakeDraftService,
    Team,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio

# Seis inscritos con su hándicap: el organizador y cinco más
HANDICAPS = [Decimal(h) for h in ("2.0", "5.0", "9.0", "13.0", "18.0", "24.0")]


async def _montar(capitanes: str = "los dos"):
    """Cerrada con seis inscritos; los capitanes son el 2.º y el 5.º por hándicap."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    comp_id = CompetitionId(creada.id)
    jugadores = [creator_id] + [UserId(uuid4()) for _ in HANDICAPS[1:]]
    async with uow:
        (organizador,) = await uow.enrollments.find_by_competition(comp_id)
        organizador.set_custom_handicap(HANDICAPS[0])
        await uow.enrollments.update(organizador)
        await uow.commit()
    for jugador, handicap in zip(jugadores[1:], HANDICAPS[1:], strict=True):
        await create_approved_enrollment(uow, creada.id, jugador, custom_handicap=handicap)
    await set_competition_status(uow, creada.id, "CLOSED")

    capitan_a, capitan_b = jugadores[1], jugadores[4]
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        if capitanes != "ninguno":
            competicion.name_captains(
                capitan_a, capitan_b, approved_player_ids=jugadores, has_teams=False
            )
        if capitanes == "solo el A":
            competicion.handle_withdrawal(capitan_b)
        await uow.competitions.update(competicion)
        await uow.commit()
    return uow, comp_id, creator_id, jugadores, (capitan_a, capitan_b)


def _use_case(uow) -> AssignTeamsUseCase:
    """El caso de uso con un repositorio de usuarios que no encuentra a nadie."""
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    return AssignTeamsUseCase(uow, repo)


async def _automatico(uow, comp_id, creator_id):
    """Reparto automático pedido por el creador."""
    return await _use_case(uow).execute(
        AssignTeamsRequestDTO(competition_id=comp_id.value, mode="AUTOMATIC"), creator_id
    )


async def _manual(uow, comp_id, creator_id, equipo_a, equipo_b):
    """Reparto manual con esas dos listas."""
    return await _use_case(uow).execute(
        AssignTeamsRequestDTO(
            competition_id=comp_id.value,
            mode="MANUAL",
            team_a_player_ids=[j.value for j in equipo_a],
            team_b_player_ids=[j.value for j in equipo_b],
        ),
        creator_id,
    )


async def test_automatico_cada_capitan_en_su_equipo_y_el_resto_por_draft():
    """Los capitanes no entran en el draft: reparte a los otros cuatro."""
    uow, comp_id, creator_id, jugadores, (capitan_a, capitan_b) = await _montar()

    reparto = await _automatico(uow, comp_id, creator_id)

    resto = [
        PlayerForDraft(user_id=j, handicap=h)
        for j, h in zip(jugadores, HANDICAPS, strict=True)
        if j not in (capitan_a, capitan_b)
    ]
    draft = SnakeDraftService()
    resultado = draft.assign_teams(resto)
    esperado_a = [capitan_a.value] + [j.value for j in draft.get_team_players(resultado, Team.A)]
    esperado_b = [capitan_b.value] + [j.value for j in draft.get_team_players(resultado, Team.B)]
    assert reparto.team_a_player_ids == esperado_a
    assert reparto.team_b_player_ids == esperado_b


async def test_automatico_sin_capitanes_sigue_como_siempre():
    """El flujo viejo convive: draft de los seis, sin nadie fijo."""
    uow, comp_id, creator_id, jugadores, _ = await _montar(capitanes="ninguno")

    reparto = await _automatico(uow, comp_id, creator_id)

    draft = SnakeDraftService()
    resultado = draft.assign_teams(
        [PlayerForDraft(user_id=j, handicap=h) for j, h in zip(jugadores, HANDICAPS, strict=True)]
    )
    assert reparto.team_a_player_ids == [j.value for j in draft.get_team_players(resultado, Team.A)]


async def test_manual_con_cada_capitan_en_su_equipo():
    """
    Given: capitanes nombrados
    When: el reparto manual pone a cada uno en el suyo
    Then: se acepta
    """
    uow, comp_id, creator_id, jugadores, (capitan_a, capitan_b) = await _montar()
    resto = [j for j in jugadores if j not in (capitan_a, capitan_b)]

    reparto = await _manual(
        uow, comp_id, creator_id, [capitan_a, *resto[:2]], [capitan_b, *resto[2:]]
    )

    assert capitan_a.value in reparto.team_a_player_ids
    assert capitan_b.value in reparto.team_b_player_ids


@pytest.mark.parametrize("error", ["A en el equipo B", "B en el equipo A", "A fuera"])
async def test_manual_un_capitan_fuera_de_su_equipo_no_se_acepta(error):
    """
    Given: capitanes nombrados
    When: el reparto manual los cambia, junta a los dos o deja fuera a uno
    Then: se rechaza y no se guarda ningún reparto
    """
    uow, comp_id, creator_id, jugadores, (capitan_a, capitan_b) = await _montar()
    resto = [j for j in jugadores if j not in (capitan_a, capitan_b)]
    equipos = {
        "A en el equipo B": ([capitan_b, *resto[:2]], [capitan_a, *resto[2:]]),
        "B en el equipo A": ([capitan_a, capitan_b, resto[0]], resto[1:]),
        "A fuera": ([resto[0], *resto[1:2]], [capitan_b, resto[2]]),
    }[error]

    with pytest.raises(CaptainOnWrongTeamError):
        await _manual(uow, comp_id, creator_id, *equipos)

    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is None


@pytest.mark.parametrize("modo", ["AUTOMATIC", "MANUAL"])
async def test_con_un_solo_capitan_pide_nombrar_al_que_falta(modo):
    """Repartir cojo dejaría un equipo sin capitán y otro con uno fijo de más."""
    uow, comp_id, creator_id, jugadores, (capitan_a, _) = await _montar(capitanes="solo el A")
    resto = [j for j in jugadores if j != capitan_a]

    with pytest.raises(CaptainMissingError):
        if modo == "AUTOMATIC":
            await _automatico(uow, comp_id, creator_id)
        else:
            await _manual(uow, comp_id, creator_id, [capitan_a, *resto[:2]], resto[2:])

    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is None


async def test_repartir_bloquea_la_fila_de_la_competicion():
    """Si no, nombrar capitanes a la vez guardaría un reparto con los capitanes viejos."""
    uow, comp_id, creator_id, _, _ = await _montar()
    llamadas = []
    original = uow.competitions.find_by_id_for_update

    async def espia(competition_id):
        """Anota con qué competición se pidió el bloqueo y deja hacer al original."""
        llamadas.append(competition_id)
        return await original(competition_id)

    uow.competitions.find_by_id_for_update = espia

    await _automatico(uow, comp_id, creator_id)

    assert llamadas == [comp_id]
