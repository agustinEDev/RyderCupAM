"""
El correo del organizador no sale nunca en la competición (BE #531).

Antes había un camino `include_email` que nadie activaba: se quita para que
no se pueda activar por descuido.
"""

import inspect
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import CreatorDTO
from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def test_the_creator_never_carries_an_email():
    creador = User(
        id=UserId(uuid4()),
        email=Email("organiza@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Orga",
        last_name="Niza",
    )
    user_uow = AsyncMock()
    user_uow.users.find_by_id.return_value = creador

    dto = await CompetitionDTOMapper._get_creator_dto(creador.id, user_uow)

    assert dto is not None
    assert "email" not in dto.model_dump()
    assert "organiza@example.com" not in dto.model_dump_json()


def test_there_is_no_way_to_ask_for_the_creator_email():
    assert "email" not in CreatorDTO.model_fields
    assert (
        "include_email" not in inspect.signature(CompetitionDTOMapper._get_creator_dto).parameters
    )
