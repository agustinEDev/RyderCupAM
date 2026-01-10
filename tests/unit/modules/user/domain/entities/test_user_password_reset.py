"""
Tests unitarios para los métodos de password reset de la entidad User.

Este archivo contiene tests que verifican:
- generate_password_reset_token(): Generación de token seguro con expiración 24h
- can_reset_password(): Validación de token y expiración
- reset_password(): Cambio de contraseña, invalidación de token, emisión de eventos

Estructura:
- TestGeneratePasswordResetToken: Tests para generación de tokens
- TestCanResetPassword: Tests para validación de tokens
- TestResetPassword: Tests para el proceso completo de reseteo
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.events.password_reset_completed_event import (
    PasswordResetCompletedEvent,
)
from src.modules.user.domain.events.password_reset_requested_event import (
    PasswordResetRequestedEvent,
)


class TestGeneratePasswordResetToken:
    """Tests para el método generate_password_reset_token()"""

    def test_generate_password_reset_token_creates_valid_token(self, sample_user_data):
        """
        Test: Generar token de reseteo válido
        Given: Usuario existente sin token previo
        When: Se llama a generate_password_reset_token()
        Then: Se genera un token URL-safe de 32 bytes, se establece expiración 24h,
              y se emite PasswordResetRequestedEvent
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        ip_address = "192.168.1.100"
        user_agent = "Mozilla/5.0 (Test Browser)"

        # Act
        token = user.generate_password_reset_token(
            ip_address=ip_address, user_agent=user_agent
        )

        # Assert
        # 1. Verificar que se generó un token no vacío
        assert token is not None
        assert len(token) > 0
        assert isinstance(token, str)

        # 2. Verificar que el token es URL-safe (no contiene caracteres especiales problemáticos)
        # secrets.token_urlsafe() genera tokens con caracteres [A-Za-z0-9_-]
        assert all(c.isalnum() or c in ["-", "_"] for c in token)

        # 3. Verificar que el token se almacenó en el usuario
        assert user.password_reset_token == token

        # 4. Verificar que se estableció la fecha de expiración (24 horas desde ahora)
        assert user.reset_token_expires_at is not None
        # Verificar que la expiración está entre 23.9 y 24.1 horas desde ahora (tolerancia de 6 minutos)
        now = datetime.now()
        expected_expiration = now + timedelta(hours=24)
        time_diff = abs(
            (user.reset_token_expires_at - expected_expiration).total_seconds()
        )
        assert time_diff < 360  # Menos de 6 minutos de diferencia

        # 5. Verificar que se actualizó updated_at
        assert user.updated_at is not None

        # 6. Verificar que se emitió el evento PasswordResetRequestedEvent
        events = user.get_domain_events()
        assert len(events) == 2  # UserRegisteredEvent + PasswordResetRequestedEvent
        # El último evento debe ser PasswordResetRequestedEvent
        event = events[-1]
        assert isinstance(event, PasswordResetRequestedEvent)
        assert event.user_id == str(user.id.value)
        assert event.email == str(user.email.value)
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent
        assert event.reset_token_expires_at == user.reset_token_expires_at

    def test_generate_password_reset_token_overwrites_previous_token(
        self, sample_user_data
    ):
        """
        Test: Generar nuevo token sobrescribe el anterior
        Given: Usuario con token previo no utilizado
        When: Se genera un nuevo token
        Then: El token anterior es reemplazado por el nuevo
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )

        # Generar primer token
        first_token = user.generate_password_reset_token(ip_address="1.1.1.1")
        first_expiration = user.reset_token_expires_at
        user.clear_domain_events()  # Limpiar eventos

        # Act: Generar segundo token (simular solicitud duplicada)
        second_token = user.generate_password_reset_token(ip_address="2.2.2.2")

        # Assert
        # 1. Los tokens son diferentes
        assert first_token != second_token

        # 2. El token actual es el segundo
        assert user.password_reset_token == second_token

        # 3. La expiración se actualizó
        assert user.reset_token_expires_at != first_expiration
        assert user.reset_token_expires_at > first_expiration

        # 4. Se emitió un nuevo evento
        events = user.get_domain_events()
        # Solo debemos tener el segundo evento ya que limpiamos después del primero
        assert len(events) == 1
        assert isinstance(events[0], PasswordResetRequestedEvent)

    def test_generate_password_reset_token_without_ip_and_user_agent(
        self, sample_user_data
    ):
        """
        Test: Generar token sin IP ni User-Agent (parámetros opcionales)
        Given: Usuario existente
        When: Se llama a generate_password_reset_token() sin parámetros opcionales
        Then: El token se genera correctamente con ip_address=None y user_agent=None
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )

        # Act
        token = user.generate_password_reset_token()

        # Assert
        assert token is not None
        assert user.password_reset_token == token

        # Verificar evento con campos opcionales en None
        events = user.get_domain_events()
        # Último evento es PasswordResetRequestedEvent
        event = events[-1]
        assert isinstance(event, PasswordResetRequestedEvent)
        assert event.ip_address is None
        assert event.user_agent is None


class TestCanResetPassword:
    """Tests para el método can_reset_password()"""

    def test_can_reset_password_returns_true_with_valid_token(self, sample_user_data):
        """
        Test: Validar token válido y no expirado
        Given: Usuario con token recién generado
        When: Se valida el token correcto
        Then: Retorna True
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Act
        result = user.can_reset_password(token)

        # Assert
        assert result is True

    def test_can_reset_password_returns_false_with_invalid_token(
        self, sample_user_data
    ):
        """
        Test: Validar token incorrecto
        Given: Usuario con token válido
        When: Se valida con un token diferente (incorrecto)
        Then: Retorna False (sin revelar información)
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        user.generate_password_reset_token()

        # Act
        result = user.can_reset_password("wrong_token_12345")

        # Assert
        assert result is False

    def test_can_reset_password_returns_false_with_expired_token(
        self, sample_user_data
    ):
        """
        Test: Validar token expirado (>24 horas)
        Given: Usuario con token expirado
        When: Se valida el token después de 25 horas
        Then: Retorna False
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Simular que pasaron 25 horas (token expirado)
        user.reset_token_expires_at = datetime.now() - timedelta(hours=1)

        # Act
        result = user.can_reset_password(token)

        # Assert
        assert result is False

    def test_can_reset_password_raises_error_when_no_active_token(
        self, sample_user_data
    ):
        """
        Test: Validar sin token activo
        Given: Usuario sin token de reseteo activo
        When: Se intenta validar un token
        Then: Lanza ValueError con mensaje específico
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        # No se genera ningún token

        # Act & Assert
        with pytest.raises(
            ValueError, match="No hay ninguna solicitud de reseteo de contraseña activa"
        ):
            user.can_reset_password("any_token")

    def test_can_reset_password_at_exact_expiration_boundary(self, sample_user_data):
        """
        Test: Validar token exactamente en el momento de expiración
        Given: Usuario con token que expira justo ahora
        When: Se valida el token en el momento exacto de expiración
        Then: Retorna False (expiración estricta)
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="CurrentPassword123!",
        )
        token = user.generate_password_reset_token()

        # Establecer expiración exactamente ahora (boundary)
        user.reset_token_expires_at = datetime.now()

        # Act
        result = user.can_reset_password(token)

        # Assert
        assert result is False


class TestResetPassword:
    """Tests para el método reset_password()"""

    def test_reset_password_successfully_changes_password(self, sample_user_data):
        """
        Test: Resetear contraseña exitosamente
        Given: Usuario con token válido
        When: Se llama a reset_password() con token correcto y nueva contraseña
        Then: La contraseña cambia, el token se invalida, y se emite PasswordResetCompletedEvent
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        old_password_hash = user.password.hashed_value
        token = user.generate_password_reset_token(ip_address="10.0.0.1")
        user.clear_domain_events()  # Limpiar evento de generación

        # Act
        new_password = "NewSecurePassword456!"
        user.reset_password(
            token=token,
            new_password=new_password,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )

        # Assert
        # 1. La contraseña cambió (hash diferente)
        assert user.password.hashed_value != old_password_hash

        # 2. La nueva contraseña es válida (se puede verificar)
        assert user.password.verify(new_password)

        # 3. El token se invalidó (uso único)
        assert user.password_reset_token is None
        assert user.reset_token_expires_at is None

        # 4. Se emitió PasswordResetCompletedEvent
        events = user.get_domain_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, PasswordResetCompletedEvent)
        assert event.user_id == str(user.id.value)
        assert event.email == str(user.email.value)
        assert event.ip_address == "10.0.0.1"
        assert event.user_agent == "Mozilla/5.0"

    def test_reset_password_raises_error_with_invalid_token(self, sample_user_data):
        """
        Test: Resetear contraseña con token inválido
        Given: Usuario con token válido
        When: Se intenta resetear con un token incorrecto
        Then: Lanza ValueError y la contraseña NO cambia
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        old_password_hash = user.password.hashed_value
        user.generate_password_reset_token()

        # Act & Assert
        with pytest.raises(ValueError, match="Token de reseteo inválido o expirado"):
            user.reset_password(token="wrong_token_xyz", new_password="NewPassword456!")

        # Verificar que la contraseña NO cambió
        assert user.password.hashed_value == old_password_hash

    def test_reset_password_raises_error_with_expired_token(self, sample_user_data):
        """
        Test: Resetear contraseña con token expirado
        Given: Usuario con token expirado (>24h)
        When: Se intenta resetear con el token expirado
        Then: Lanza ValueError y la contraseña NO cambia
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        old_password_hash = user.password.hashed_value
        token = user.generate_password_reset_token()

        # Simular expiración (hace 2 horas)
        user.reset_token_expires_at = datetime.now() - timedelta(hours=2)

        # Act & Assert
        with pytest.raises(ValueError, match="Token de reseteo inválido o expirado"):
            user.reset_password(token=token, new_password="NewPassword456!")

        # Verificar que la contraseña NO cambió
        assert user.password.hashed_value == old_password_hash

    def test_reset_password_raises_error_with_weak_password(self, sample_user_data):
        """
        Test: Resetear contraseña con contraseña débil (no cumple política)
        Given: Usuario con token válido
        When: Se intenta resetear con contraseña que no cumple la política de seguridad
        Then: Lanza error de validación del Password VO
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()

        # Act & Assert: Contraseña débil (sin mayúsculas, números, ni símbolos)
        # El error específico puede variar según qué requisito falle primero
        with pytest.raises(Exception):  # InvalidPasswordError o ValueError
            user.reset_password(
                token=token,
                new_password="weakpassword",  # No cumple: mayúsculas, números, símbolos
            )

    def test_reset_password_invalidates_token_after_use(self, sample_user_data):
        """
        Test: Token se invalida después del primer uso (uso único)
        Given: Usuario con token válido
        When: Se resetea la contraseña exitosamente
        Then: El token se invalida y NO se puede usar una segunda vez
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()

        # Act: Primer reseteo (exitoso)
        user.reset_password(token=token, new_password="NewPassword456!")

        # Assert: Segundo intento con el mismo token falla
        with pytest.raises(
            ValueError, match="No hay ninguna solicitud de reseteo de contraseña activa"
        ):
            user.reset_password(token=token, new_password="AnotherPassword789!")

    def test_reset_password_without_ip_and_user_agent(self, sample_user_data):
        """
        Test: Resetear contraseña sin IP ni User-Agent (parámetros opcionales)
        Given: Usuario con token válido
        When: Se resetea sin proporcionar ip_address ni user_agent
        Then: El reseteo funciona correctamente con valores None
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        user.clear_domain_events()

        # Act
        user.reset_password(token=token, new_password="NewPassword456!")

        # Assert
        assert user.password_reset_token is None

        # Verificar evento con campos opcionales en None
        events = user.get_domain_events()
        event = events[0]
        assert isinstance(event, PasswordResetCompletedEvent)
        assert event.ip_address is None
        assert event.user_agent is None

    def test_reset_password_updates_timestamp(self, sample_user_data):
        """
        Test: Resetear contraseña actualiza updated_at
        Given: Usuario con token válido
        When: Se resetea la contraseña
        Then: El campo updated_at se actualiza a la hora actual
        """
        # Arrange
        user = User.create(
            first_name=sample_user_data["name"],
            last_name=sample_user_data["surname"],
            email_str=sample_user_data["email"],
            plain_password="OldPassword123!",
        )
        token = user.generate_password_reset_token()
        old_updated_at = user.updated_at

        # Act: Esperar un pequeño momento para asegurar que el timestamp cambie
        import time

        time.sleep(0.01)  # 10ms
        user.reset_password(token=token, new_password="NewPassword456!")

        # Assert
        assert user.updated_at > old_updated_at
