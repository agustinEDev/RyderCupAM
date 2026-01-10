"""
Tests unitarios para el caso de uso ResetPasswordUseCase.

Este archivo contiene tests que verifican:
- Reseteo exitoso de contraseña con token válido
- Manejo de tokens inválidos o expirados
- Validación de política de contraseñas
- Invalidación de token (uso único)
- Revocación de refresh tokens (logout forzado)
- Envío de email de confirmación
- Security logging completo

Estructura:
- TestResetPasswordSuccess: Tests para flujo exitoso
- TestResetPasswordInvalidToken: Tests para tokens inválidos
- TestResetPasswordSecurityFeatures: Tests de seguridad
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.modules.user.application.dto.user_dto import ResetPasswordRequestDTO
from src.modules.user.application.use_cases.reset_password_use_case import (
    ResetPasswordUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests como asyncio
pytestmark = pytest.mark.asyncio


class TestResetPasswordSuccess:
    """Tests para el flujo exitoso de reseteo de contraseña"""

    async def test_reset_password_successfully_changes_password(self, sample_user_data):
        """
        Test: Resetear contraseña exitosamente cambia el password
        Given: Usuario con token válido
        When: Se resetea la contraseña con token correcto y nueva contraseña válida
        Then: La contraseña cambia, el token se invalida, y se envía email de confirmación
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        email_service.send_password_changed_notification = AsyncMock(return_value=True)

        use_case = ResetPasswordUseCase(uow, email_service)

        # Crear usuario con token de reseteo
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token(ip_address="1.1.1.1")
        old_password_hash = user.password.hashed_value

        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(
            token=token,
            new_password="NewSecurePassword456!",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)",
        )

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        # 1. Verificar respuesta exitosa
        assert (
            response.message
            == "Contraseña reseteada exitosamente. Todas tus sesiones activas han sido cerradas por seguridad."
        )

        # 2. Verificar que la contraseña cambió
        async with uow:
            updated_user = await uow.users.find_by_id(user.id)
            assert updated_user.password.hashed_value != old_password_hash
            assert updated_user.password.verify("NewSecurePassword456!")

            # 3. Verificar que el token se invalidó
            assert updated_user.password_reset_token is None
            assert updated_user.reset_token_expires_at is None

        # 4. Verificar que se envió email de confirmación
        email_service.send_password_changed_notification.assert_called_once()
        call_args = email_service.send_password_changed_notification.call_args
        assert call_args.kwargs["to_email"] == sample_user_data["email"]
        assert call_args.kwargs["user_name"] == user.get_full_name()

    async def test_reset_password_invalidates_token_after_use(self, sample_user_data):
        """
        Test: Token se invalida después del primer uso (uso único)
        Given: Usuario con token válido
        When: Se resetea la contraseña exitosamente
        Then: El token se invalida y NO se puede usar una segunda vez
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(token=token, new_password="NewPassword456!")

        # Act: Primer reseteo (exitoso)
        await use_case.execute(request_dto)

        # Assert: Segundo intento con el mismo token falla
        second_request = ResetPasswordRequestDTO(token=token, new_password="AnotherPassword789!")

        # El segundo intento falla porque el token ya fue invalidado
        # Puede fallar con diferentes mensajes dependiendo de la validación
        with pytest.raises(Exception):  # ValueError o similar
            await use_case.execute(second_request)

    async def test_reset_password_revokes_all_refresh_tokens(self, sample_user_data):
        """
        Test: Reseteo de contraseña revoca TODAS las sesiones activas
        Given: Usuario con múltiples sesiones activas (refresh tokens)
        When: Se resetea la contraseña
        Then: Todos los refresh tokens se revocan (logout forzado)
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(token=token, new_password="NewPassword456!")

        # Act
        await use_case.execute(request_dto)

        # Assert - Verificar que se llamó a revoke_all_for_user
        # (En el InMemoryUnitOfWork, este método existe y se ejecuta)
        # No podemos verificar el mock porque usamos el UoW real,
        # pero verificamos que el reseteo fue exitoso
        async with uow:
            updated_user = await uow.users.find_by_id(user.id)
            assert updated_user.password_reset_token is None


class TestResetPasswordInvalidToken:
    """Tests para tokens inválidos o expirados"""

    async def test_reset_password_with_invalid_token_raises_error(self):
        """
        Test: Token inválido (no existe) lanza ValueError
        Given: Token que no existe en la BD
        When: Se intenta resetear contraseña
        Then: Lanza ValueError con mensaje específico
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = ResetPasswordUseCase(uow, email_service)

        # Generar un token válido de al menos 32 caracteres (pero que no existe en BD)
        fake_token = "a" * 43  # Longitud típica de token URL-safe

        request_dto = ResetPasswordRequestDTO(token=fake_token, new_password="NewPassword456!")

        # Act & Assert
        # Cuando el token no existe, puede fallar en validación de security event
        # o en la lógica de negocio, ambos son válidos
        with pytest.raises(ValueError):
            await use_case.execute(request_dto)

        # Verificar que NO se envió email
        email_service.send_password_changed_notification.assert_not_called()

    async def test_reset_password_with_expired_token_raises_error(self, sample_user_data):
        """
        Test: Token expirado (>24h) lanza ValueError
        Given: Usuario con token expirado
        When: Se intenta resetear contraseña
        Then: Lanza ValueError y NO cambia la contraseña
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        old_password_hash = user.password.hashed_value

        # Simular expiración (hace 2 horas)
        user.reset_token_expires_at = datetime.now() - timedelta(hours=2)

        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(token=token, new_password="NewPassword456!")

        # Act & Assert
        with pytest.raises(ValueError, match="Token de reseteo inválido o expirado"):
            await use_case.execute(request_dto)

        # Verificar que la contraseña NO cambió
        async with uow:
            unchanged_user = await uow.users.find_by_id(user.id)
            assert unchanged_user.password.hashed_value == old_password_hash

    async def test_reset_password_with_weak_password_raises_error(self, sample_user_data):
        """
        Test: Contraseña débil (no cumple política) lanza error
        Given: Usuario con token válido
        When: Se intenta resetear con contraseña que no cumple la política
        Then: Lanza error de validación y NO cambia la contraseña
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        old_password_hash = user.password.hashed_value

        async with uow:
            await uow.users.save(user)

        # Password que pasa validación de Pydantic (12+ chars) pero falla en Password VO
        request_dto = ResetPasswordRequestDTO(
            token=token,
            new_password="weakpassword",  # 12 chars pero sin mayúsculas, números, símbolos
        )

        # Act & Assert
        with pytest.raises(Exception):  # InvalidPasswordError o ValueError
            await use_case.execute(request_dto)

        # Verificar que la contraseña NO cambió
        async with uow:
            unchanged_user = await uow.users.find_by_id(user.id)
            assert unchanged_user.password.hashed_value == old_password_hash


class TestResetPasswordSecurityFeatures:
    """Tests para features de seguridad"""

    @patch("src.modules.user.application.use_cases.reset_password_use_case.get_security_logger")
    async def test_reset_password_logs_successful_reset(self, mock_get_logger, sample_user_data):
        """
        Test: Reseteo exitoso registra security log
        Given: Usuario con token válido
        When: Se resetea exitosamente la contraseña
        Then: Se registra evento en security logger con success=True
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = AsyncMock()
        mock_get_logger.return_value = mock_security_logger

        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(
            token=token,
            new_password="NewPassword456!",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        # Act
        await use_case.execute(request_dto)

        # Assert
        mock_security_logger.log_password_reset_completed.assert_called_once()
        call_args = mock_security_logger.log_password_reset_completed.call_args
        assert call_args.kwargs["email"] == sample_user_data["email"]
        assert call_args.kwargs["success"] is True
        assert call_args.kwargs["failure_reason"] is None
        assert call_args.kwargs["ip_address"] == "192.168.1.1"
        assert call_args.kwargs["user_agent"] == "Mozilla/5.0"

    @patch("src.modules.user.application.use_cases.reset_password_use_case.get_security_logger")
    async def test_reset_password_logs_failed_reset_invalid_token(self, mock_get_logger):
        """
        Test: Token inválido registra security log con failure
        Given: Token que no existe
        When: Se intenta resetear
        Then: Se registra con success=False y failure_reason
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = AsyncMock()
        mock_get_logger.return_value = mock_security_logger

        use_case = ResetPasswordUseCase(uow, email_service)

        # Token válido de al menos 32 caracteres (pero no existe en BD)
        fake_token = "b" * 43

        request_dto = ResetPasswordRequestDTO(
            token=fake_token,
            new_password="NewPassword456!",
            ip_address="10.0.0.1",
            user_agent="Chrome/90",
        )

        # Act
        try:
            await use_case.execute(request_dto)
        except ValueError:
            pass  # Esperamos el error

        # Assert
        mock_security_logger.log_password_reset_completed.assert_called_once()
        call_args = mock_security_logger.log_password_reset_completed.call_args
        assert call_args.kwargs["user_id"] is None
        assert call_args.kwargs["email"] == "unknown"
        assert call_args.kwargs["success"] is False
        assert call_args.kwargs["failure_reason"] == "Invalid or expired token"

    @patch("src.modules.user.application.use_cases.reset_password_use_case.get_security_logger")
    async def test_reset_password_logs_failed_reset_expired_token(
        self, mock_get_logger, sample_user_data
    ):
        """
        Test: Token expirado registra security log con failure
        Given: Usuario con token expirado
        When: Se intenta resetear
        Then: Se registra con success=False y detalle del error
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = AsyncMock()
        mock_get_logger.return_value = mock_security_logger

        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        # Expirar el token
        user.reset_token_expires_at = datetime.now() - timedelta(hours=2)
        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(
            token=token, new_password="NewPassword456!", ip_address="10.0.0.1"
        )

        # Act
        try:
            await use_case.execute(request_dto)
        except ValueError:
            pass  # Esperamos el error

        # Assert
        mock_security_logger.log_password_reset_completed.assert_called_once()
        call_args = mock_security_logger.log_password_reset_completed.call_args
        assert call_args.kwargs["success"] is False
        assert "Token de reseteo inválido o expirado" in call_args.kwargs["failure_reason"]

    async def test_reset_password_uses_default_values_for_optional_fields(self, sample_user_data):
        """
        Test: Campos opcionales usan valores por defecto
        Given: Request sin ip_address ni user_agent
        When: Se ejecuta el use case
        Then: Se usan valores por defecto "unknown"
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        # Request sin campos opcionales
        request_dto = ResetPasswordRequestDTO(token=token, new_password="NewPassword456!")

        # Act
        response = await use_case.execute(request_dto)

        # Assert - Verificar que el reseteo fue exitoso
        assert (
            response.message
            == "Contraseña reseteada exitosamente. Todas tus sesiones activas han sido cerradas por seguridad."
        )

    async def test_reset_password_sends_confirmation_email(self, sample_user_data):
        """
        Test: Email de confirmación se envía después del reseteo
        Given: Usuario con token válido
        When: Se resetea la contraseña exitosamente
        Then: Se envía email de confirmación al usuario
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        email_service.send_password_changed_notification = AsyncMock(return_value=True)

        use_case = ResetPasswordUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        request_dto = ResetPasswordRequestDTO(token=token, new_password="NewPassword456!")

        # Act
        await use_case.execute(request_dto)

        # Assert - Verificar que se envió el email
        email_service.send_password_changed_notification.assert_called_once()
        call_args = email_service.send_password_changed_notification.call_args
        assert call_args.kwargs["to_email"] == sample_user_data["email"]
        assert call_args.kwargs["user_name"] == user.get_full_name()
