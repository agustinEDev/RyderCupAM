"""
Tests de integración para verificar que los eventos de login se registran correctamente.

Verifica que el LoginUserUseCase registra eventos UserLoggedInEvent cuando
se ejecuta con éxito un login.
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.events.user_logged_in_event import UserLoggedInEvent
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


@pytest.mark.asyncio
class TestLoginUserUseCaseEventIntegration:
    """Tests de integración para eventos en LoginUserUseCase."""

    async def test_login_successful_registers_user_logged_in_event(self):
        """
                Test: Login exitoso registra un evento UserLoggedInEvent.

                Verifica que cuando un usuario hace login exitoso, se registra
        correctamente un evento de dominio UserLoggedInEvent.
        """
        # Arrange
        user_id = UserId.generate()
        email = Email("test@example.com")
        password = Password.from_plain_text("P@ssw0rd123!")

        user = User(
            id=user_id,
            email=email,
            password=password,
            first_name="John",
            last_name="Doe",
        )

        # Mock del UoW
        mock_uow = AsyncMock()
        mock_uow.users.find_by_email.return_value = user
        mock_uow.users.save = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        token_service = JWTTokenService()
        use_case = LoginUserUseCase(mock_uow, token_service)

        request = LoginRequestDTO(email="test@example.com", password="P@ssw0rd123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        assert response.access_token is not None

        # Verificar que el usuario tiene eventos de dominio
        assert user.has_domain_events()

        # Obtener eventos de dominio
        events = user.get_domain_events()

        # Verificar que hay al menos un evento UserLoggedInEvent
        login_events = [e for e in events if isinstance(e, UserLoggedInEvent)]
        assert len(login_events) == 1

        # Verificar el contenido del evento
        login_event = login_events[0]
        assert login_event.user_id == str(user_id.value)
        assert login_event.logged_in_at is not None
        assert login_event.login_method == "email"

        # Verificar que se llamó save para persistir el evento
        mock_uow.users.save.assert_called_once_with(user)

    async def test_login_failed_does_not_register_event(self):
        """
        Test: Login fallido no registra eventos.

        Verifica que cuando un login falla (usuario no existe o password
        incorrecto), no se registran eventos de dominio.
        """
        # Arrange - Usuario no existe
        mock_uow = AsyncMock()
        mock_uow.users.find_by_email.return_value = None

        token_service = JWTTokenService()
        use_case = LoginUserUseCase(mock_uow, token_service)

        request = LoginRequestDTO(email="noexiste@example.com", password="P@ssw0rd123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

        # Verificar que no se llamó save (no hay usuario para persistir eventos)
        mock_uow.users.save.assert_not_called()

    async def test_login_wrong_password_does_not_register_event(self):
        """
        Test: Login con password incorrecto no registra eventos de login exitoso.

        Verifica que cuando existe el usuario pero el password es incorrecto,
        no se registran eventos de login exitoso (pero SÍ se guarda para
        incrementar el contador de intentos fallidos - Account Lockout v1.13.0).
        """
        # Arrange
        user_id = UserId.generate()
        email = Email("test@example.com")
        password = Password.from_plain_text("C0rr3ctP@ss123!")

        user = User(
            id=user_id,
            email=email,
            password=password,
            first_name="John",
            last_name="Doe",
        )

        mock_uow = AsyncMock()
        mock_uow.users.find_by_email.return_value = user

        token_service = JWTTokenService()
        use_case = LoginUserUseCase(mock_uow, token_service)

        request = LoginRequestDTO(
            email="test@example.com",
            password="WrongPass123",  # Password incorrecto
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

        # Verificar que el usuario NO tiene eventos de dominio (no hay LoginSuccessEvent)
        assert not user.has_domain_events()

        # Account Lockout (v1.13.0): SÍ se llama save para incrementar failed_login_attempts
        mock_uow.users.save.assert_called_once_with(user)
