"""
Los capitanes de una privada en la respuesta (tabla del 27 oct 2026; revisor).

Quien no está en una privada no ve a ninguno de sus jugadores: tampoco quiénes
son sus capitanes y vices, que con su id se sacan de su perfil.

| Quién mira                                  | Capitanes y vices |
|---------------------------------------------|-------------------|
| Privada, de fuera (o invitado pendiente)    | null              |
| Privada, aprobado                           | los ids           |
| Privada, organizador o admin                | los ids           |
| Pública, cualquiera                         | los ids           |
"""

from dataclasses import replace
from uuid import uuid4

from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
)

CARGOS = (
    "team_a_captain_id",
    "team_b_captain_id",
    "team_a_vice_captain_id",
    "team_b_vice_captain_id",
)


async def _ryder(visibilidad=Visibility.PRIVATE):
    uow = InMemoryUnitOfWork()
    creador = UserId(uuid4())
    creada = await create_competition(uow, creador)
    capitanes = {cargo: UserId(uuid4()) for cargo in CARGOS}
    async with uow:
        comp = await uow.competitions.find_by_id(CompetitionId(creada.id))
        comp._visibility = visibilidad
        comp._ryder_cup = replace(comp.ryder_cup, **capitanes)
        await uow.competitions.update(comp)
    return uow, comp, creador, capitanes


async def _cargos(uow, comp, quien, is_admin=False) -> dict:
    async with uow:
        dto = await CompetitionDTOMapper.to_response_dto(comp, quien, uow, is_admin=is_admin)
    return {cargo: getattr(dto, cargo) for cargo in CARGOS}


def _ids(capitanes) -> dict:
    return {cargo: uid.value for cargo, uid in capitanes.items()}


async def test_de_fuera_de_una_privada_no_ve_a_sus_capitanes():
    uow, comp, _, _ = await _ryder()

    assert await _cargos(uow, comp, UserId(uuid4())) == dict.fromkeys(CARGOS)


async def test_el_aprobado_de_una_privada_si():
    uow, comp, _, capitanes = await _ryder()
    yo = UserId(uuid4())
    await create_approved_enrollment(uow, comp.id.value, yo)

    assert await _cargos(uow, comp, yo) == _ids(capitanes)


async def test_el_organizador_y_un_admin_si():
    uow, comp, creador, capitanes = await _ryder()
    # Que organice sin jugar: si no, ve a los capitanes por estar aprobado
    async with uow:
        suya = await uow.enrollments.find_by_user_and_competition(creador, comp.id)
        await uow.enrollments.delete(suya.id)

    assert await _cargos(uow, comp, creador) == _ids(capitanes)
    assert await _cargos(uow, comp, UserId(uuid4()), is_admin=True) == _ids(capitanes)


async def test_en_una_publica_cualquiera():
    uow, comp, _, capitanes = await _ryder(Visibility.PUBLIC)

    assert await _cargos(uow, comp, UserId(uuid4())) == _ids(capitanes)
