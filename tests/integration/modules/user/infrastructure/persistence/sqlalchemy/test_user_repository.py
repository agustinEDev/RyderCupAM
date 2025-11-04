import pytest
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import SQLAlchemyUserRepository

pytestmark = pytest.mark.asyncio

async def test_save_and_get_user(db_session):
    """
    Verifica que un usuario se puede guardar y recuperar correctamente.
    """
    # Arrange: Crear un usuario y el repositorio
    user = User.create(
        first_name="Agustin",
        last_name="Dominguez",
        email_str="agustin.test@example.com",
        plain_password="ValidPassword123!"
    )
    repository = SQLAlchemyUserRepository(db_session)

    # Act: Guardar el usuario y hacer commit
    await repository.save(user)
    db_session.commit()

    # Assert: Recuperar el usuario y verificar que es el mismo
    retrieved_user = await repository.find_by_id(user.id)
    
    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.first_name == "Agustin"
    assert retrieved_user.last_name == "Dominguez"
    assert retrieved_user.email.value == "agustin.test@example.com"
