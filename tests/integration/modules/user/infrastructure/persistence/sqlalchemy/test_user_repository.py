import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

# Marcar todos los tests de este fichero como 'integration'
pytestmark = pytest.mark.integration


async def test_save_and_get_user(db_session):
    """
    Verifica que un usuario se puede guardar y recuperar correctamente.
    """
    # Arrange
    user = User.create(
        first_name="Agustin",
        last_name="Dominguez",
        email_str="agustin.test@example.com",
        plain_password="ValidPassword123!",
    )
    repository = SQLAlchemyUserRepository(db_session)

    # Act
    await repository.save(user)
    await db_session.commit()

    # Assert
    retrieved_user = await repository.find_by_id(user.id)

    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.email.value == "agustin.test@example.com"


async def test_find_by_id_for_update_locks_and_returns_the_row(db_session):
    """
    find_by_id_for_update (SELECT ... FOR UPDATE) debe seguir devolviendo el
    usuario correcto — se usa para serializar operaciones read-modify-write
    concurrentes (p.ej. podar el historial de avatares subidos).
    """
    user = User.create(
        first_name="Marta",
        last_name="Lopez",
        email_str="marta.test@example.com",
        plain_password="ValidPassword123!",
    )
    repository = SQLAlchemyUserRepository(db_session)
    await repository.save(user)
    await db_session.commit()

    retrieved_user = await repository.find_by_id_for_update(user.id)

    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.email.value == "marta.test@example.com"


async def test_search_by_partial_name_excludes_deactivated_accounts(db_session):
    """
    La búsqueda de jugadores no puede devolver cuentas desactivadas.

    Cualquier usuario registrado puede buscar por nombre, así que dejarlas
    visibles expone a quien pidió desactivarse y permite mandarle solicitudes
    de amistad que nunca verá. Es además lo que impide que el usuario de
    sistema del importador de campos aparezca entre los jugadores.
    """
    repository = SQLAlchemyUserRepository(db_session)

    active = User.create(
        first_name="Alicia",
        last_name="Buscable",
        email_str="alicia.buscable@example.com",
        plain_password="ValidPassword123!",
    )
    deactivated = User.create(
        first_name="Alberto",
        last_name="Buscable",
        email_str="alberto.buscable@example.com",
        plain_password="ValidPassword123!",
    )
    deactivated.deactivate(deactivated_by_user_id=str(active.id.value))

    await repository.save(active)
    await repository.save(deactivated)
    await db_session.commit()

    results = await repository.search_by_partial_name("Buscable")

    found_ids = {user.id for user in results}
    assert active.id in found_ids
    assert deactivated.id not in found_ids


async def test_search_by_partial_name_finds_a_reactivated_account(db_session):
    """
    Reactivar una cuenta la devuelve a la búsqueda.

    El filtro mira el estado actual, no un histórico: una cuenta que vuelve
    tiene que poder volver a recibir solicitudes de amistad.
    """
    repository = SQLAlchemyUserRepository(db_session)

    admin = User.create(
        first_name="Admin",
        last_name="Reactivador",
        email_str="admin.reactivador@example.com",
        plain_password="ValidPassword123!",
    )
    user = User.create(
        first_name="Regreso",
        last_name="Reactivado",
        email_str="regreso.reactivado@example.com",
        plain_password="ValidPassword123!",
    )
    user.deactivate(deactivated_by_user_id=str(admin.id.value))
    user.reactivate(reactivated_by_user_id=str(admin.id.value))

    await repository.save(admin)
    await repository.save(user)
    await db_session.commit()

    results = await repository.search_by_partial_name("Reactivado")

    assert user.id in {found.id for found in results}
