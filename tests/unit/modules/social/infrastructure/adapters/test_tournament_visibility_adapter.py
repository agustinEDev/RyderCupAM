"""El adaptador que dice que torneos son privados ahora (tabla del 22 oct 2026, E)."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.social.infrastructure.adapters.tournament_visibility_adapter import (
    TournamentVisibilityAdapter,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import create_competition

pytestmark = pytest.mark.asyncio


async def _torneo(uow, visibility: Visibility) -> str:
    creada = await create_competition(uow, UserId(uuid4()))
    async with uow:
        competicion = await uow.competitions.find_by_id(CompetitionId(creada.id))
        competicion.update_info(visibility=visibility)
        await uow.competitions.update(competicion)
    return str(creada.id)


async def test_devuelve_solo_los_privados():
    uow = InMemoryCompetitionUnitOfWork()
    privado = await _torneo(uow, Visibility.PRIVATE)
    publico = await _torneo(uow, Visibility.PUBLIC)

    privados = await TournamentVisibilityAdapter(uow).private_ids([privado, publico])

    assert privados == {privado}


async def test_un_id_ilegible_o_que_no_existe_no_cuenta_como_privado():
    """Uno borrado ya tiene su limpieza; un id ilegible no puede tumbar el feed."""
    uow = InMemoryCompetitionUnitOfWork()

    privados = await TournamentVisibilityAdapter(uow).private_ids(["no-es-un-uuid", str(uuid4())])

    assert privados == set()


async def test_sin_ids_no_lee_nada():
    assert (
        await TournamentVisibilityAdapter(InMemoryCompetitionUnitOfWork()).private_ids([]) == set()
    )
