"""
Tests de integración: cuándo guarda el LoginUserUseCase al usuario.

Con éxito, una vez; sin usuario, nunca; con la contraseña mala, una vez para
contar el intento fallido (Account Lockout v1.13.0).
"""

from unittest.mock import AsyncMock

import pytest

from src.config.freno_del_login import FrenoDelLoginEnMemoria
from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.security.jwt_handler import JWTTokenService
from tests.unit.modules.user.application.use_cases._registro_falso import (
    registro_de_dispositivo_falso,
)


@pytest.mark.asyncio
class TestLoginUserUseCaseGuardado:
    """Tests de integración: cuándo guarda el LoginUserUseCase al usuario."""

    async def test_login_successful_saves_user_once(self):
        """
        Test: Login exitoso guarda al usuario una vez.
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
        # El login relee al usuario con la fila bloqueada, falle o no (BE #282)
        mock_uow.users.find_by_id_for_update.return_value = user
        mock_uow.users.save = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)

        token_service = JWTTokenService()

        # Mock del RegisterDeviceUseCase (v1.13.0 - Device Fingerprinting)
        # Toda sesión registra su dispositivo (BE #737): una respuesta válida
        mock_register_device = registro_de_dispositivo_falso()

        use_case = LoginUserUseCase(
            mock_uow,
            token_service,
            mock_register_device,
            AsyncMock(),
            FrenoDelLoginEnMemoria(),
            AsyncMock(),
            security_audit=SecurityAuditLogger(),
        )

        request = LoginRequestDTO(email="test@example.com", password="P@ssw0rd123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        assert response.access_token is not None

        # Una vez: acertar ya no pone el respaldo a cero (BE #732), así que no hay otro guardado antes
        mock_uow.users.save.assert_called_with(user)
        assert mock_uow.users.save.call_count == 1

    async def test_login_unknown_user_does_not_save(self):
        """
        Test: Login de un usuario que no existe no guarda nada.
        """
        # Arrange - Usuario no existe
        mock_uow = AsyncMock()
        mock_uow.users.find_by_email.return_value = None

        token_service = JWTTokenService()

        # Mock del RegisterDeviceUseCase (v1.13.0 - Device Fingerprinting)
        mock_register_device = AsyncMock()

        use_case = LoginUserUseCase(
            mock_uow,
            token_service,
            mock_register_device,
            AsyncMock(),
            FrenoDelLoginEnMemoria(),
            AsyncMock(),
            security_audit=SecurityAuditLogger(),
        )

        request = LoginRequestDTO(email="noexiste@example.com", password="P@ssw0rd123!")

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

        # Verificar que no se llamó save (no hay usuario que guardar)
        mock_uow.users.save.assert_not_called()

    async def test_login_wrong_password_saves_failed_attempt(self):
        """
        Test: Login con password incorrecto guarda al usuario para incrementar
        el contador de intentos fallidos (Account Lockout v1.13.0).
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
        # El login relee al usuario con la fila bloqueada, falle o no (BE #282)
        mock_uow.users.find_by_id_for_update.return_value = user

        token_service = JWTTokenService()

        # Mock del RegisterDeviceUseCase (v1.13.0 - Device Fingerprinting)
        mock_register_device = AsyncMock()

        use_case = LoginUserUseCase(
            mock_uow,
            token_service,
            mock_register_device,
            AsyncMock(),
            FrenoDelLoginEnMemoria(),
            AsyncMock(),
            security_audit=SecurityAuditLogger(),
        )

        request = LoginRequestDTO(
            email="test@example.com",
            password="WrongPass123",  # Password incorrecto
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

        # Account Lockout (v1.13.0): SÍ se llama save para incrementar failed_login_attempts
        mock_uow.users.save.assert_called_once_with(user)
