"""
Tests para DeleteCompetitionUseCase.puede_borrar (BE #347).

La ficha necesita saber si quien la mira puede borrarla ahora, para enseñar o no
el botón. La regla ya vive en `execute`: quién (creador o admin), el estado
(`Competition.allows_deletion`) y el calendario (`_tiene_calendario`). Aquí no se
reescribe: se comprueba que la pregunta y el borrado de verdad dicen SIEMPRE lo
mismo, en cada combinación de estado, calendario y rol. Si algún día divergen,
el botón mentiría, y este test lo dice antes.
"""

from datetime import date
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
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

# Cada situación: cómo se deja la competición y si tiene calendario
SITUACIONES = {
    "borrador": ("DRAFT", False),
    "abierta": ("ACTIVE", False),
    "cerrada": ("CLOSED", False),
    "en juego": ("IN_PROGRESS", True),
    "cancelada sin calendario": ("CANCELLED", False),
    "cancelada con calendario": ("CANCELLED", True),
}
ROLES = ("creador", "admin", "otro")


async def _montar(uow: InMemoryUnitOfWork, creator_id: UserId, estado: str, con_calendario: bool):
    """Crea la competición, la lleva al estado pedido y, si toca, le pone una ronda."""
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
        if estado in ("CLOSED", "IN_PROGRESS"):
            competition.close_enrollments()
        if estado == "IN_PROGRESS":
            competition.start()
        if estado == "CANCELLED":
            competition.cancel()
        await uow.competitions.update(competition)
        if con_calendario:
            await uow.rounds.add(
                Round.create(
                    competition_id=competition_id,
                    golf_course_id=GolfCourseId(uuid4()),
                    round_date=date(2030, 6, 1),
                    session_type=SessionType.MORNING,
                    match_format=MatchFormat.SINGLES,
                )
            )
        await uow.commit()

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
    Then: la respuesta coincide con lo que pasa al borrar
    """
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    estado, con_calendario = SITUACIONES[situacion]
    competition_id, estado_real = await _montar(uow, creator_id, estado, con_calendario)
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


async def test_puede_borrar_casos_que_importan():
    """
    Los que la tabla cubre, dichos en claro: una cancelada sin calendario SÍ,
    una cancelada con calendario NO, y alguien ajeno nunca.
    """
    for situacion, rol, esperado in [
        ("cancelada sin calendario", "creador", True),
        ("abierta", "creador", True),
        ("borrador", "admin", True),
        ("cancelada con calendario", "creador", False),
        ("cerrada", "creador", False),
        ("abierta", "otro", False),
    ]:
        uow = InMemoryUnitOfWork()
        creator_id = UserId(uuid4())
        estado, con_calendario = SITUACIONES[situacion]
        competition_id, _ = await _montar(uow, creator_id, estado, con_calendario)
        user_id, is_admin = _quien(rol, creator_id)

        dice = await DeleteCompetitionUseCase(uow).puede_borrar(
            competition_id, user_id, is_admin=is_admin
        )

        assert dice is esperado, f"{situacion} / {rol}"


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
    competition_id, _ = await _montar(uow, creator_id, "ACTIVE", False)

    await DeleteCompetitionUseCase(uow).puede_borrar(competition_id, creator_id, is_admin=False)

    async with uow:
        assert await uow.competitions.find_by_id(competition_id) is not None
