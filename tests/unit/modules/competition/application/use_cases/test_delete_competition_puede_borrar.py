"""
Tests para DeleteCompetitionUseCase.puede_borrar (BE #347).

La ficha necesita saber si quien la mira puede borrarla ahora, para enseñar o no
el botón. La regla vive en `execute`: quién (creador o admin), el estado
(`CompetitionStatus.allows_deletion`) y que no haya nada jugado
(`_tiene_algo_jugado`). Aquí se comprueban dos cosas en cada combinación de
situación y rol: que la pregunta y el borrado de verdad dicen SIEMPRE lo mismo
—si divergen, el botón miente— y que lo que dicen es la regla acordada.

La regla, decidida con el dueño del producto el 22 sep: se protege lo jugado, no
lo montado. Tener calendario no impide borrar; un solo golpe anotado, un
walkover o un partido terminado, sí. Y lo que está en juego o terminado, nunca.
"""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    DeleteCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import NotCompetitionCreatorError
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import montar_calendario

pytestmark = pytest.mark.asyncio

# Cada situación: el estado, hasta dónde se jugó su calendario (None si no
# tiene) y si el creador o un admin pueden borrarla
SITUACIONES = {
    "borrador": ("DRAFT", None, True),
    "abierta": ("ACTIVE", None, True),
    # Reabierta tras montar el calendario: sin jugar no hay nada que perder
    "abierta con calendario sin jugar": ("ACTIVE", "sin jugar", True),
    # Ya jugada y devuelta a ACTIVE con `revert-status` + `reopen-enrollments`
    "abierta con un golpe": ("ACTIVE", "golpe propio", False),
    "cerrada": ("CLOSED", None, True),
    "cerrada con calendario sin jugar": ("CLOSED", "sin jugar", True),
    # La anotación se abre sola a la hora de la sesión (BE #305): las tarjetas
    # existen, vacías, sin que nadie haya jugado
    "cerrada con partido abierto sin golpes": ("CLOSED", "empezado", True),
    "cerrada con un golpe propio": ("CLOSED", "golpe propio", False),
    "cerrada con un golpe del marcador": ("CLOSED", "golpe del marcador", False),
    # Una raya no lleva número, pero es un hoyo jugado
    "cerrada con una raya": ("CLOSED", "raya", False),
    "cerrada con un walkover": ("CLOSED", "walkover", False),
    "cerrada con un partido concedido": ("CLOSED", "concedido", False),
    "cerrada con un partido terminado": ("CLOSED", "terminado", False),
    "en juego": ("IN_PROGRESS", None, False),
    "en juego sin jugar": ("IN_PROGRESS", "sin jugar", False),
    "terminada": ("COMPLETED", None, False),
    "cancelada sin calendario": ("CANCELLED", None, True),
    "cancelada con calendario sin jugar": ("CANCELLED", "sin jugar", True),
    "cancelada con un golpe": ("CANCELLED", "golpe propio", False),
    "cancelada con un walkover": ("CANCELLED", "walkover", False),
}
ROLES = ("creador", "admin", "otro")


async def _montar(uow: InMemoryUnitOfWork, creator_id: UserId, estado: str, como: str | None):
    """Crea la competición, la lleva al estado pedido y, si toca, le cuelga el calendario."""
    programada = estado == "DRAFT"
    request = CreateCompetitionRequestDTO(
        name="Ryder Cup 2030",
        start_date=date(2030, 6, 1),
        end_date=date(2030, 6, 3),
        main_country="ES",
        play_mode="SCRATCH",
        # Programada lejos: nace esperando su apertura, que es lo que es un borrador
        enrollment_opens_days_before=5 if programada else None,
    )
    creada = await CreateCompetitionUseCase(uow, LocationBuilder(uow.countries)).execute(
        request, creator_id
    )
    competition_id = CompetitionId(creada.id)

    async with uow:
        competition = await uow.competitions.find_by_id(competition_id)
        if estado in ("CLOSED", "IN_PROGRESS", "COMPLETED"):
            competition.close_enrollments()
        if estado in ("IN_PROGRESS", "COMPLETED"):
            competition.start()
        if estado == "COMPLETED":
            competition.complete()
        if estado == "CANCELLED":
            competition.cancel()
        await uow.competitions.update(competition)
        await uow.commit()

    if como is not None:
        await montar_calendario(uow, competition_id, como)

    return competition_id, competition.status.value


def _quien(rol: str, creator_id: UserId) -> tuple[UserId, bool]:
    if rol == "creador":
        return creator_id, False
    if rol == "admin":
        return UserId(uuid4()), True
    return UserId(uuid4()), False


@pytest.mark.parametrize("rol", ROLES)
@pytest.mark.parametrize("situacion", list(SITUACIONES))
async def test_puede_borrar_dice_lo_mismo_que_el_borrado(situacion, rol):
    """
    Given: una competición en cada situación y alguien con cada rol
    When: se pregunta si puede borrarla y luego se intenta de verdad
    Then: la respuesta coincide con lo que pasa al borrar, y los dos con la regla
    """
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    estado, como, borrable = SITUACIONES[situacion]
    competition_id, estado_real = await _montar(uow, creator_id, estado, como)
    assert estado_real == estado, f"el montaje dejó {estado_real}, no {estado}"
    user_id, is_admin = _quien(rol, creator_id)
    use_case = DeleteCompetitionUseCase(uow)

    dice = await use_case.puede_borrar(competition_id, user_id, is_admin=is_admin)

    try:
        await use_case.execute(
            DeleteCompetitionRequestDTO(competition_id=competition_id.value),
            user_id,
            is_admin=is_admin,
        )
        borra = True
    except (NotCompetitionCreatorError, CompetitionNotDeletableError):
        borra = False

    assert dice is borra
    assert borra is (borrable and rol != "otro")


async def test_puede_borrar_una_que_no_existe_es_no():
    uow = InMemoryUnitOfWork()

    dice = await DeleteCompetitionUseCase(uow).puede_borrar(
        CompetitionId(uuid4()), UserId(uuid4()), is_admin=True
    )

    assert dice is False


async def test_puede_borrar_no_borra_nada():
    """Preguntar no puede tener efectos: la competición sigue ahí."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    competition_id, _ = await _montar(uow, creator_id, "ACTIVE", None)

    await DeleteCompetitionUseCase(uow).puede_borrar(competition_id, creator_id, is_admin=False)

    async with uow:
        assert await uow.competitions.find_by_id(competition_id) is not None


@pytest.mark.parametrize("estado", ["IN_PROGRESS", "COMPLETED"])
async def test_puede_borrar_no_recorre_el_calendario_si_el_estado_ya_dice_que_no(estado):
    """Se pregunta en cada ficha: un torneo en juego no debe costar N consultas."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    competition_id, _ = await _montar(uow, creator_id, estado, "sin jugar")
    uow.rounds.find_by_competition = AsyncMock(side_effect=AssertionError("no debía mirarlo"))

    dice = await DeleteCompetitionUseCase(uow).puede_borrar(
        competition_id, creator_id, is_admin=False
    )

    assert dice is False
