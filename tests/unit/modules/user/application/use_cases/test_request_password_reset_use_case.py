"""
Tests unitarios para el caso de uso RequestPasswordResetUseCase.

Este archivo contiene tests que verifican:
- Solicitud exitosa con email existente
- Manejo de email no existente (timing attack prevention)
- Envío de email con enlace de reseteo
- Security logging completo
- Sin retardo artificial: el correo sale en segundo plano (fase 3)

Estructura:
- TestRequestPasswordResetSuccess: Tests para flujo exitoso
- TestRequestPasswordResetEmailNotFound: Tests para email no existente
- TestRequestPasswordResetSecurityFeatures: Tests de seguridad
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.user_dto import (
    RequestPasswordResetRequestDTO,
)
from src.modules.user.application.use_cases.request_password_reset_use_case import (
    RequestPasswordResetUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.token_hash import hash_del_enlace
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger

# Marcar todos los tests como asyncio
pytestmark = pytest.mark.asyncio


class TestRequestPasswordResetSuccess:
    """Tests para el flujo exitoso de solicitud de reseteo"""

    async def test_request_password_reset_with_existing_email_sends_email(self, sample_user_data):
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

        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        # Crear usuario existente
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"],
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)",
        )

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        # 1. Verificar respuesta con mensaje genérico
        assert (
            response.message
            == "Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña."
        )
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
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"], ip_address="10.0.0.1"
        )

        # Act
        await use_case.execute(request_dto)

        # Assert
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            # Token debe ser string no vacío y URL-safe
            assert isinstance(saved_user.password_reset_token, str)
            assert len(saved_user.password_reset_token) > 0
            assert all(c.isalnum() or c in ["-", "_"] for c in saved_user.password_reset_token)
            # Debe tener expiración
            assert saved_user.reset_token_expires_at is not None

    async def test_request_password_reset_includes_correct_reset_link(self, sample_user_data):
        """
        Test: Enlace de reseteo tiene formato correcto
        Given: Usuario solicitando reseteo
        When: Se envía el email
        Then: El enlace incluye el token y apunta al frontend
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(email=sample_user_data["email"])

        # Act
        await use_case.execute(request_dto)

        # Assert
        call_args = email_service.send_password_reset_email.call_args
        reset_link = call_args.kwargs["reset_link"]

        # Verificar formato del enlace
        assert reset_link.startswith("http")
        assert "/reset-password/" in reset_link
        # Verificar que contiene el token (la cuenta guarda su SHA-256, fase 3)
        token = reset_link.rsplit("/", 1)[1]
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            assert saved_user.password_reset_token == hash_del_enlace(token)

    async def test_reset_link_uses_the_injected_frontend_url(self, sample_user_data):
        """
        Given: el caso de uso construido con la URL del frontend (con barra final)
        When: se pide el reseteo para un usuario que existe
        Then: el enlace apunta a esa URL, sin doble barra: ya no lee
            `src.config.settings` (auditoría 9 nov 2026)
        """
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="https://app.ejemplo.test/",
            security_audit=SecurityAuditLogger(),
        )
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        async with uow:
            await uow.users.save(user)

        await use_case.execute(RequestPasswordResetRequestDTO(email=sample_user_data["email"]))

        reset_link = email_service.send_password_reset_email.call_args.kwargs["reset_link"]
        assert reset_link.startswith("https://app.ejemplo.test/reset-password/")


class TestRequestPasswordResetEmailNotFound:
    """Tests para el flujo cuando el email no existe"""

    async def test_request_password_reset_with_nonexistent_email_returns_generic_message(self):
        """
        Test: Email no existente, mensaje genérico. Ya sin retardo artificial: el correo
        de quien sí existe sale en segundo plano (fase 3, B-2), así que no hay envío que
        imitar (test_enlaces_y_freno_del_reset)
        Given: Email que NO existe en el sistema
        When: Se solicita reseteo
        Then: Se retorna mensaje genérico y no se envía nada
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        request_dto = RequestPasswordResetRequestDTO(
            email="nonexistent@example.com", ip_address="1.2.3.4"
        )

        # Act
        response = await use_case.execute(request_dto)

        # Assert
        # 1. Retorna el MISMO mensaje genérico
        assert (
            response.message
            == "Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña."
        )
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
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        request_existing = RequestPasswordResetRequestDTO(email="exists@test.com")
        request_nonexistent = RequestPasswordResetRequestDTO(email="nonexistent@test.com")

        # Crear usuario existente
        user = User.create(
            first_name="Test",
            last_name="User",
            email_str="exists@test.com",
            plain_password="Segura-Prueba123!",
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

    async def test_request_password_reset_logs_successful_request(self, sample_user_data):
        """
        Test: Solicitud exitosa registra security log
        Given: Usuario existente
        When: Se solicita reseteo exitosamente
        Then: Se registra evento en security logger con success=True
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = MagicMock()

        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=mock_security_logger,
        )

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(
            email=sample_user_data["email"],
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
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

    async def test_request_password_reset_logs_failed_request(self):
        """
        Test: Email no existente registra security log con failure
        Given: Email no registrado
        When: Se solicita reseteo
        Then: Se registra con success=False y failure_reason
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        mock_security_logger = MagicMock()

        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=mock_security_logger,
        )

        request_dto = RequestPasswordResetRequestDTO(
            email="nonexistent@example.com",
            ip_address="10.0.0.1",
            user_agent="Chrome/90",
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
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        async with uow:
            await uow.users.save(user)

        # Request sin campos opcionales
        request_dto = RequestPasswordResetRequestDTO(email=sample_user_data["email"])

        # Act
        await use_case.execute(request_dto)

        # Assert - Verificar que el usuario tiene token (implica que se procesó correctamente)
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            assert saved_user.password_reset_token is not None

    async def test_request_password_reset_overwrites_previous_token(self, sample_user_data):
        """
        Test: Nueva solicitud sobrescribe token anterior
        Given: Usuario con token de reseteo previo
        When: Se solicita nuevo reseteo
        Then: El token anterior se reemplaza por uno nuevo
        """
        # Arrange
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        # Generar primer token directamente
        first_token = user.generate_password_reset_token()
        async with uow:
            await uow.users.save(user)

        request_dto = RequestPasswordResetRequestDTO(email=sample_user_data["email"])

        # Act - Segunda solicitud
        await use_case.execute(request_dto)

        # Assert
        async with uow:
            saved_user = await uow.users.find_by_id(user.id)
            # Token debe ser diferente al primero
            assert saved_user.password_reset_token != first_token
            assert saved_user.password_reset_token is not None


class TestPasswordResetEmailIgnoresTheAlias:
    """
    Los correos de la cuenta van con el nombre LEGAL, no con el alias.

    Hablan de la cuenta —verificarla, recuperar la contraseña—, así que se
    dirigen a quien es su titular. El alias es para la pantalla.
    """

    async def test_the_email_greets_the_legal_name_not_the_alias(self, sample_user_data):
        """
        Given: Un usuario con alias
        When: Pide recuperar la contraseña
        Then: El correo lleva su nombre completo, y no el alias
        """
        uow = InMemoryUnitOfWork()
        email_service = AsyncMock()
        email_service.send_password_reset_email = AsyncMock(return_value=True)
        use_case = RequestPasswordResetUseCase(
            uow,
            email_service,
            frontend_url="http://localhost:5173",
            security_audit=SecurityAuditLogger(),
        )

        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        user.update_profile(alias="Chuchi")
        async with uow:
            await uow.users.save(user)

        await use_case.execute(
            RequestPasswordResetRequestDTO(
                email=sample_user_data["email"],
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0 (Test Browser)",
            )
        )

        call_args = email_service.send_password_reset_email.call_args
        assert call_args.kwargs["user_name"] == user.get_full_name()
        assert call_args.kwargs["user_name"] != "Chuchi"
        assert user.display_name == "Chuchi"
