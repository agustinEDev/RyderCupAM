"""
Buscar por nombre completo con dos cuentas que se llaman igual (S-16, auditoría del
18 nov 2026).

`scalar_one_or_none()` lanzaba MultipleResultsFound y la búsqueda daba 500. Con dos o más
cuentas activas con ese nombre la respuesta es «no encontrado»: devolver una de las dos
podría llevar una invitación a quien no es.

  B4-1 una cuenta con ese nombre                         -> esa
  B4-2 dos activas con el mismo nombre                    -> None (no 500)
  B4-3 ninguna                                           -> None
  B4-4 dos que casan partiendo el nombre de forma distinta -> None
  B4-5 una activa y una desactivada con el mismo nombre  -> la activa
"""

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration

CONTRASENA = "ValidPassword123!"


async def _guarda(db_session, nombre: str, apellidos: str, correo: str, activa: bool = True):
    usuario = User.create(
        first_name=nombre, last_name=apellidos, email_str=correo, plain_password=CONTRASENA
    )
    if not activa:
        usuario.deactivate()
    await SQLAlchemyUserRepository(db_session).save(usuario)
    await db_session.commit()
    return usuario


async def test_b4_1_a_single_match_is_found(db_session):
    """Una cuenta con ese nombre: la devuelve, como antes."""
    ana = await _guarda(db_session, "Ana", "Ruiz", "ana.ruiz@example.com")

    encontrado = await SQLAlchemyUserRepository(db_session).find_by_full_name("Ana Ruiz")

    assert encontrado is not None and encontrado.id == ana.id


async def test_b4_2_two_active_homonyms_give_not_found(db_session):
    """Dos activas que se llaman igual: None en vez de MultipleResultsFound (500)."""
    await _guarda(db_session, "Ana", "Ruiz", "ana.uno@example.com")
    await _guarda(db_session, "Ana", "Ruiz", "ana.dos@example.com")

    assert await SQLAlchemyUserRepository(db_session).find_by_full_name("ana ruiz") is None


async def test_b4_3_no_match_gives_not_found(db_session):
    """Nadie con ese nombre, aunque haya casi iguales (CodeRabbit): None, como antes."""
    await _guarda(db_session, "Nadie", "Ruiz", "nadie.ruiz@example.com")
    await _guarda(db_session, "Ana", "Nunca", "ana.nunca@example.com")

    assert await SQLAlchemyUserRepository(db_session).find_by_full_name("Nadie Nunca") is None


@pytest.mark.parametrize(("nombre", "apellidos"), [("Ana", "María López"), ("Ana María", "López")])
async def test_b4_4_each_split_matches_on_its_own(db_session, nombre, apellidos):
    """Cada forma de partir «Ana María López» encuentra a su persona si está sola."""
    persona = await _guarda(db_session, nombre, apellidos, "ana.sola@example.com")

    encontrado = await SQLAlchemyUserRepository(db_session).find_by_full_name("Ana María López")

    assert encontrado is not None and encontrado.id == persona.id


async def test_b4_4_two_people_matching_different_splits_give_not_found(db_session):
    """«Ana María López»: «Ana» + «María López» y «Ana María» + «López» son dos personas."""
    await _guarda(db_session, "Ana", "María López", "ana.m1@example.com")
    await _guarda(db_session, "Ana María", "López", "ana.m2@example.com")

    encontrado = await SQLAlchemyUserRepository(db_session).find_by_full_name("Ana María López")

    assert encontrado is None


async def test_b4_5_a_deactivated_homonym_does_not_count(db_session):
    """Una activa y otra desactivada con el mismo nombre: la activa (F7)."""
    activa = await _guarda(db_session, "Luis", "Gil", "luis.uno@example.com")
    await _guarda(db_session, "Luis", "Gil", "luis.dos@example.com", activa=False)

    encontrado = await SQLAlchemyUserRepository(db_session).find_by_full_name("Luis Gil")

    assert encontrado is not None and encontrado.id == activa.id


async def test_b4_6_repeated_spaces_do_not_matter(db_session):
    """Espacios repetidos en lo guardado o en lo buscado no cuentan, como en memoria."""
    ana = await _guarda(db_session, "Ana  María", "López", "ana.espacios@example.com")
    repositorio = SQLAlchemyUserRepository(db_session)

    assert (await repositorio.find_by_full_name("Ana María López")).id == ana.id
    assert (await repositorio.find_by_full_name("ana   maría  lópez")).id == ana.id
