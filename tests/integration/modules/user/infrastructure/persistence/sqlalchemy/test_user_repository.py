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
