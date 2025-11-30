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
