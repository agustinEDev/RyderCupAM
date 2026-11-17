"""
El nombre del organizador con la regla del nombre real (SB-08, 17 nov 2026).

Pública: su nombre real a la vista, y su alias además si tiene, para ponerlo debajo.
Privada: su nombre visible (el alias si tiene); su nombre y apellidos solo para él y
los admin. Antes iban a cualquiera que viera la competición.
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


async def test_public_shows_the_real_name_and_the_alias_below():
    """
    Given: Una pública y un organizador con alias
    When: Cualquiera la mira
    Then: Su nombre real a la vista, nombre y apellidos, y el alias aparte
    """
    creador, user_uow = _uow_con("Trinx")

    dto = await CompetitionDTOMapper._get_creator_dto(
        creador.id, user_uow, Visibility.PUBLIC, ve_el_nombre_legal=False
    )

    assert dto.display_name == "Orga Niza"
    assert (dto.first_name, dto.last_name) == ("Orga", "Niza")
    assert dto.alias == "Trinx"


async def test_private_with_alias_hides_the_legal_name_from_others():
    """
    Given: Una privada y un organizador con alias
    When: La mira otro jugador
    Then: Solo su alias
    """
    creador, user_uow = _uow_con("Trinx")

    dto = await CompetitionDTOMapper._get_creator_dto(
        creador.id, user_uow, Visibility.PRIVATE, ve_el_nombre_legal=False
    )

    assert dto.display_name == "Trinx"
    assert (dto.first_name, dto.last_name) == ("", "")
    assert dto.alias is None


async def test_private_with_alias_keeps_the_legal_name_for_him_and_admins():
    """
    Given: Una privada y un organizador con alias
    When: La mira él o un admin
    Then: Va también su nombre real
    """
    creador, user_uow = _uow_con("Trinx")

    dto = await CompetitionDTOMapper._get_creator_dto(
        creador.id, user_uow, Visibility.PRIVATE, ve_el_nombre_legal=True
    )

    assert dto.display_name == "Trinx"
    assert (dto.first_name, dto.last_name) == ("Orga", "Niza")


async def test_private_without_alias_shows_his_name():
    """
    Given: Una privada y un organizador sin alias
    When: La mira otro jugador
    Then: Su nombre, que es lo único que tiene
    """
    creador, user_uow = _uow_con(None)

    dto = await CompetitionDTOMapper._get_creator_dto(
        creador.id, user_uow, Visibility.PRIVATE, ve_el_nombre_legal=False
    )

    assert dto.display_name == "Orga Niza"
    assert (dto.first_name, dto.last_name) == ("Orga", "Niza")


async def test_private_organizer_who_plays_follows_his_own_choice():
    """
    Given: Una privada; el organizador, con alias, juega en ella y eligió su nombre real
    When: La mira otro jugador
    Then: Su nombre real, como en la lista de inscritos: no dos nombres para el mismo
    """
    creador, user_uow = _uow_con("Trinx")

    dto = await CompetitionDTOMapper._get_creator_dto(
        creador.id,
        user_uow,
        Visibility.PRIVATE,
        ve_el_nombre_legal=False,
        eligio_su_nombre=AsyncMock(return_value=True),
    )

    assert dto.display_name == "Orga Niza"
    assert (dto.first_name, dto.last_name) == ("Orga", "Niza")


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
            creador.id,
            user_uow,
            visibility,
            ve_el_nombre_legal=False,
            eligio_su_nombre=lectura,
        )

        lectura.assert_not_awaited()
