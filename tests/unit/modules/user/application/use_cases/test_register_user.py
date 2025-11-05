import pytest

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO
from src.modules.user.application.use_cases.register_user import RegisterUserUseCase
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestRegisterUserUseCase:
    """
    Suite de tests para el caso de uso RegisterUserUseCase.
    """

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    async def test_should_register_user_successfully(self, uow: InMemoryUnitOfWork):
        """
        Verifica que un usuario se registra correctamente cuando los datos son válidos
        y el email no existe previamente.
        """
        # Arrange
        use_case = RegisterUserUseCase(uow)
        request_dto = RegisterUserRequestDTO(
            email="test.user@example.com",
            password="ValidPass123",
            first_name="Test",
            last_name="User",
        )

        # Act
        user_response = await use_case.execute(request_dto)

        # Assert
        # 1. Verificar que la respuesta del DTO es correcta
        assert user_response.email == request_dto.email
        assert user_response.first_name == request_dto.first_name
        assert user_response.id is not None

        # 2. Verificar que el usuario fue realmente guardado en la persistencia
        async with uow:
            user_id_vo = UserId(user_response.id)
            saved_user = await uow.users.find_by_id(user_id_vo)
            assert saved_user is not None
            assert str(saved_user.email) == request_dto.email

    async def test_should_raise_error_when_email_already_exists(
        self, uow: InMemoryUnitOfWork
    ):
        """
        Verifica que se lanza la excepción UserAlreadyExistsError si se intenta
        registrar un usuario con un email que ya existe.
        """
        # Arrange: Primero, creamos un usuario existente
        use_case = RegisterUserUseCase(uow)
        existing_user_request = RegisterUserRequestDTO(
            email="existing.user@example.com",
            password="ValidPass123",
            first_name="Existing",
            last_name="User",
        )
        await use_case.execute(existing_user_request)

        # Ahora, intentamos registrar otro usuario con el MISMO email
        new_request_dto = RegisterUserRequestDTO(
            email="existing.user@example.com",
            password="AnotherValidPass456",
            first_name="Another",
            last_name="User",
        )

        # Act & Assert
        with pytest.raises(UserAlreadyExistsError, match="ya está registrado"):
            await use_case.execute(new_request_dto)
