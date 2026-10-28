"""
Los países de la competición en su respuesta, leídos una vez (27 oct 2026, PR 2).

La ubicación («Spain, France») y la lista salen de la misma lectura: el
principal primero y luego los adyacentes, y uno que no existe no sale.
"""

from uuid import uuid4

from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from tests.unit.modules.competition.application.use_cases.helpers import create_competition


async def _respuesta(*codigos):
    uow = InMemoryUnitOfWork()
    creada = await create_competition(uow, UserId(uuid4()))
    async with uow:
        comp = await uow.competitions.find_by_id(CompetitionId(creada.id))
        comp._location = Location(*(CountryCode(c) for c in codigos))
        dto = await CompetitionDTOMapper.to_response_dto(comp, UserId(uuid4()), uow)
    return dto


async def test_el_principal_y_sus_adyacentes():
    dto = await _respuesta("ES", "FR", "PT")

    assert dto.location == "Spain, France, Portugal"
    assert [p.code for p in dto.countries] == ["ES", "FR", "PT"]
    assert [p.name_es for p in dto.countries] == ["España", "Francia", "Portugal"]


async def test_solo_el_principal():
    dto = await _respuesta("ES")

    assert dto.location == "Spain"
    assert [p.code for p in dto.countries] == ["ES"]


async def test_uno_que_no_existe_no_sale():
    dto = await _respuesta("ES", "ZZ")

    assert dto.location == "Spain"
    assert [p.code for p in dto.countries] == ["ES"]
