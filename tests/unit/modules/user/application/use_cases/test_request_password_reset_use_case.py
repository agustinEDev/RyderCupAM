"""
Tests unitarios para el caso de uso RequestPasswordResetUseCase.

Este archivo contiene tests que verifican:
- Solicitud exitosa con email existente
- Manejo de email no existente (timing attack prevention)
- Envío de email con enlace de reseteo
- Security logging completo
- Delay artificial para prevenir enumeración

Estructura:
- TestRequestPasswordResetSuccess: Tests para flujo exitoso
- TestRequestPasswordResetEmailNotFound: Tests para email no existente
- TestRequestPasswordResetSecurityFeatures: Tests de seguridad
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.modules.user.application.dto.user_dto import (
    RequestPasswordResetRequestDTO,
)
from src.modules.user.application.use_cases.request_password_reset_use_case import (
    RequestPasswordResetUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests como asyncio
pytestmark = pytest.mark.asyncio


class TestRequestPasswordResetSuccess:
    """Tests para el flujo exitoso de solicitud de reseteo"""

    async def test_request_password_reset_with_existing_email_sends_email(
        self, sample_user_data
    ):
        """
        Test: Solicitar reseteo con email existente envía email
        Given: Usuario existente en el sistema
        When: Se solicita reseteo de contraseña
        Then: Se genera token, se envía email, y se retorna mensaje genérico
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        email_service.send_password_reset_email = AsyncMock(return_value=True)

        use_case = RequestPasswordResetUseCase(uow, email_service)

        # Crear usuario existente
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!"
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"],
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)"
        )

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        # 1. Verificar respuesta con mensaje genérico
        assert response.message == "Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña."
        assert response.email == sample_user_data["email"]

        # 2. Verificar que se envió el email
        email_service.send_password_reset_email.assert_called_once()
        call_args = email_service.send_password_reset_email.call_args
        assert call_args.kwargs["to_email"] == sample_user_data["email"]
        assert call_args.kwargs["user_name"] == user.get_full_name()
        assert "reset_link" in call_args.kwargs
        assert "/reset-password/" in call_args.kwargs["reset_link"]

        # 3. Verificar que el usuario tiene token de reseteo
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            assert saved_user is not None
            assert saved_user.password_reset_token is not None
            assert saved_user.reset_token_expires_at is not None

    async def test_request_password_reset_generates_valid_token(self, sample_user_data):
        """
        Test: Solicitar reseteo genera token seguro
        Given: Usuario existente
        When: Se solicita reseteo
        Then: Se genera token URL-safe con expiración 24h
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!"
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"],
            ip_address="10.0.0.1"
        )

        # Act
        await use_case.execute(request_dto)

        # Assert
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            # Token debe ser string no vacío y URL-safe
            assert isinstance(saved_user.password_reset_token, str)
            assert len(saved_user.password_reset_token) > 0
            assert all(
                c.isalnum() or c in ['-', '_']
                for c in saved_user.password_reset_token
            )
            # Debe tener expiración
            assert saved_user.reset_token_expires_at is not None

    async def test_request_password_reset_includes_correct_reset_link(
        self, sample_user_data
    ):
        """
        Test: Enlace de reseteo tiene formato correcto
        Given: Usuario solicitando reseteo
        When: Se envía el email
        Then: El enlace incluye el token y apunta al frontend
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!"
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"]
        )

        # Act
        await use_case.execute(request_dto)

        # Assert
        call_args = email_service.send_password_reset_email.call_args
        reset_link = call_args.kwargs["reset_link"]

        # Verificar formato del enlace
        assert reset_link.startswith("http")
        assert "/reset-password/" in reset_link
        # Verificar que contiene el token
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            assert saved_user.password_reset_token in reset_link


class TestRequestPasswordResetEmailNotFound:
    """Tests para el flujo cuando el email no existe"""

    async def test_request_password_reset_with_nonexistent_email_applies_delay(self):
        """
        Test: Email no existente aplica delay artificial (timing attack prevention)
        Given: Email que NO existe en el sistema
        When: Se solicita reseteo
        Then: Se aplica delay de 0.5s y se retorna mensaje genérico
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(uow, email_service)

        request_dto = RequestPasswordResetRequestDTO(
            email="nonexistent@example.com",
            ip_address="1.2.3.4"
        )

        # Act
        import time
        start_time = time.time()
        response = await use_case.execute(request_dto)
        elapsed_time = time.time() - start_time

        # Assert
        # 1. Verificar que se aplicó el delay (al menos 0.4s con tolerancia)
        assert elapsed_time >= 0.4  # 0.5s de delay - tolerancia de 0.1s

        # 2. Retorna el MISMO mensaje genérico
        assert response.message == "Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña."
        assert response.email == "nonexistent@example.com"

        # 3. NO se envió email
        email_service.send_password_reset_email.assert_not_called()

    async def test_request_password_reset_nonexistent_email_returns_generic_message(
        self,
    ):
        """
        Test: Email no existente retorna mensaje genérico (sin revelar existencia)
        Given: Email no registrado
        When: Se solicita reseteo
        Then: Se retorna el mismo mensaje que si existiera (previene enumeración)
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(uow, email_service)

        request_existing = RequestPasswordResetRequestDTO(email="exists@test.com")
        request_nonexistent = RequestPasswordResetRequestDTO(
            email="nonexistent@test.com"
        )

        # Crear usuario existente
        user = User.create(
            first_name="Test",
            last_name="User",
            email_str="exists@test.com",
            plain_password="Password123!"
        )
        async with uow:
            await uow.users.save(user)

        # Act
        response_existing = await use_case.execute(request_existing)
        response_nonexistent = await use_case.execute(request_nonexistent)

        # Assert - Los mensajes deben ser IDÉNTICOS
        assert response_existing.message == response_nonexistent.message
        assert (
            response_existing.message
            == "Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña."
        )


class TestRequestPasswordResetSecurityFeatures:
    """Tests para features de seguridad"""

    @patch("src.modules.user.application.use_cases.request_password_reset_use_case.get_security_logger")
    async def test_request_password_reset_logs_successful_request(
        self, mock_get_logger, sample_user_data
    ):
        """
        Test: Solicitud exitosa registra security log
        Given: Usuario existente
        When: Se solicita reseteo exitosamente
        Then: Se registra evento en security logger con success=True
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = AsyncMock()
        mock_get_logger.return_value = mock_security_logger

        use_case = RequestPasswordResetUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!"
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"],
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        # Act
        await use_case.execute(request_dto)

        # Assert
        mock_security_logger.log_password_reset_requested.assert_called_once()
        call_args = mock_security_logger.log_password_reset_requested.call_args
        assert call_args.kwargs["email"] == sample_user_data["email"]
        assert call_args.kwargs["success"] is True
        assert call_args.kwargs["failure_reason"] is None
        assert call_args.kwargs["ip_address"] == "192.168.1.1"
        assert call_args.kwargs["user_agent"] == "Mozilla/5.0"

    @patch("src.modules.user.application.use_cases.request_password_reset_use_case.get_security_logger")
    async def test_request_password_reset_logs_failed_request(self, mock_get_logger):
        """
        Test: Email no existente registra security log con failure
        Given: Email no registrado
        When: Se solicita reseteo
        Then: Se registra con success=False y failure_reason
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = AsyncMock()
        mock_get_logger.return_value = mock_security_logger

        use_case = RequestPasswordResetUseCase(uow, email_service)

        request_dto = RequestPasswordResetRequestDTO(
            email="nonexistent@example.com",
            ip_address="10.0.0.1",
            user_agent="Chrome/90"
        )

        # Act
        await use_case.execute(request_dto)

        # Assert
        mock_security_logger.log_password_reset_requested.assert_called_once()
        call_args = mock_security_logger.log_password_reset_requested.call_args
        assert call_args.kwargs["email"] == "nonexistent@example.com"
        assert call_args.kwargs["success"] is False
        assert call_args.kwargs["failure_reason"] == "Email not found (not revealed to client)"
        assert call_args.kwargs["ip_address"] == "10.0.0.1"
        assert call_args.kwargs["user_agent"] == "Chrome/90"

    async def test_request_password_reset_uses_default_values_for_optional_fields(
        self, sample_user_data
    ):
        """
        Test: Campos opcionales usan valores por defecto
        Given: Request sin ip_address ni user_agent
        When: Se ejecuta el use case
        Then: Se usan valores por defecto "unknown"
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!"
        )
        async with uow:
            await uow.users.save(user)

        # Request sin campos opcionales
        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"]
        )

        # Act
        await use_case.execute(request_dto)

        # Assert - Verificar que el usuario tiene token (implica que se procesó correctamente)
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            assert saved_user.password_reset_token is not None

    async def test_request_password_reset_overwrites_previous_token(
        self, sample_user_data
    ):
        """
        Test: Nueva solicitud sobrescribe token anterior
        Given: Usuario con token de reseteo previo
        When: Se solicita nuevo reseteo
        Then: El token anterior se reemplaza por uno nuevo
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(uow, email_service)

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!"
        )
        # Generar primer token directamente
        first_token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"]
        )

        # Act - Segunda solicitud
        await use_case.execute(request_dto)

        # Assert
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            # Token debe ser diferente al primero
            assert saved_user.password_reset_token != first_token
            assert saved_user.password_reset_token is not None
