"""
El nombre del organizador con la regla del nombre real (SB-08, 17 nov 2026).

Qué va delante: en una pública, su nombre real; en una privada, lo que eligió si juega
en ella y, si no, su nombre visible (el alias si tiene). Nombre, apellidos y alias van
siempre: el alias es un apodo, no un dato oculto (Agustín, 17 nov 2026).
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


def _uow_con(alias: str | None):
    creador = User(
        id=UserId(uuid4()),
        email=Email("organiza@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Orga",
        last_name="Niza",
    )
    if alias:
        creador.update_profile(alias=alias)
    user_uow = AsyncMock()
    user_uow.users.find_by_id.return_value = creador
    return creador, user_uow


@pytest.mark.parametrize(
    "visibility, eligio, delante",
    [
        (Visibility.PUBLIC, None, "Orga Niza"),
        (Visibility.PRIVATE, None, "Trinx"),
        (Visibility.PRIVATE, True, "Orga Niza"),
        (Visibility.PRIVATE, False, "Trinx"),
    ],
    ids=["publica", "privada-no-juega", "privada-juega-con-nombre", "privada-juega-con-alias"],
)
async def test_the_name_in_front_follows_the_rule_and_everything_goes(visibility, eligio, delante):
    """
    Given: Un organizador con alias, que juega o no en su competición
    When: Se arma su ficha
    Then: Delante, el que toca; nombre, apellidos y alias, siempre
    """
    creador, user_uow = _uow_con("Trinx")

    dto = await CompetitionDTOMapper._get_creator_dto(
        creador.id,
        user_uow,
        visibility,
        eligio_su_nombre=None if eligio is None else AsyncMock(return_value=eligio),
    )

    assert dto.display_name == delante
    assert (dto.first_name, dto.last_name, dto.alias) == ("Orga", "Niza", "Trinx")


async def test_without_alias_his_name_and_no_alias():
    """
    Given: Un organizador sin alias, en una privada
    When: Se arma su ficha
    Then: Su nombre, y alias vacío
    """
    creador, user_uow = _uow_con(None)

    dto = await CompetitionDTOMapper._get_creator_dto(creador.id, user_uow, Visibility.PRIVATE)

    assert dto.display_name == "Orga Niza"
    assert dto.alias is None


async def test_the_organizer_enrolment_is_not_read_when_it_cannot_change_the_name():
    """
    Given: Una pública, o una privada con un organizador sin alias
    When: Se arma el organizador
    Then: No se lee su inscripción: el nombre sería el mismo (la ficha tiene tope de
          consultas)
    """
    for visibility, alias in ((Visibility.PUBLIC, "Trinx"), (Visibility.PRIVATE, None)):
        creador, user_uow = _uow_con(alias)
        lectura = AsyncMock(return_value=True)

        await CompetitionDTOMapper._get_creator_dto(
            creador.id, user_uow, visibility, eligio_su_nombre=lectura
        )

        lectura.assert_not_awaited()
