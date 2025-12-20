"""
Tests unitarios para Security Events (Domain Layer).

Verifica que los eventos de auditoría de seguridad:
- Se crean correctamente con todos los campos requeridos
- Ajustan automáticamente el nivel de severity
- Validan campos obligatorios
- Serializan correctamente a diccionario

Cobertura:
- LoginAttemptEvent (success/failure, severity auto-ajuste)
- LogoutEvent (severity LOW)
- RefreshTokenUsedEvent (validación refresh_token_id)
- RefreshTokenRevokedEvent (severity según reason)
- PasswordChangedEvent (severity HIGH)
- EmailChangedEvent (severity HIGH)
- AccessDeniedEvent (campos completos)
- RateLimitExceededEvent (validación request_count)
"""

import pytest
from datetime import datetime

from src.shared.domain.events.security_events import (
    AccessDeniedEvent,
    EmailChangedEvent,
    LoginAttemptEvent,
    LogoutEvent,
    PasswordChangedEvent,
    RateLimitExceededEvent,
    RefreshTokenRevokedEvent,
    RefreshTokenUsedEvent,
    SecuritySeverity,
)


class TestLoginAttemptEvent:
    """Tests para LoginAttemptEvent - Evento más crítico del sistema"""

    def test_login_success_creates_event_with_medium_severity(self):
        """
        Test: Login exitoso crea evento con severity MEDIUM

        Given: Datos válidos de login exitoso
        When: Se crea un LoginAttemptEvent con success=True
        Then: El evento se crea con severity MEDIUM (auto-ajustado)
        """
        # Arrange
        user_id = "user-123"
        email = "user@example.com"
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

        # Act
        event = LoginAttemptEvent(
            user_id=user_id,
            email=email,
            success=True,
            failure_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assert
        assert event.user_id == user_id
        assert event.email == email
        assert event.success is True
        assert event.failure_reason is None
        assert event.severity == SecuritySeverity.MEDIUM  # Auto-ajustado
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent
        assert event.aggregate_type == "Security"

    def test_login_failure_creates_event_with_high_severity(self):
        """
        Test: Login fallido crea evento con severity HIGH

        Given: Datos de login fallido con failure_reason
        When: Se crea un LoginAttemptEvent con success=False
        Then: El evento se crea con severity HIGH (auto-ajustado)
        """
        # Arrange
        email = "attacker@malicious.com"
        ip_address = "203.0.113.45"
        user_agent = "curl/7.68.0"
        failure_reason = "Invalid credentials"

        # Act
        event = LoginAttemptEvent(
            user_id=None,  # Login falló, no hay user_id
            email=email,
            success=False,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assert
        assert event.user_id is None
        assert event.email == email
        assert event.success is False
        assert event.failure_reason == failure_reason
        assert event.severity == SecuritySeverity.HIGH  # Auto-ajustado (posible ataque)
        assert event.aggregate_type == "Security"

    def test_login_failure_without_reason_raises_error(self):
        """
        Test: Login fallido sin failure_reason lanza ValueError

        Given: Datos de login fallido SIN failure_reason
        When: Se intenta crear LoginAttemptEvent
        Then: Se lanza ValueError porque failure_reason es obligatorio
        """
        # Arrange
        invalid_data = {
            "user_id": None,
            "email": "user@example.com",
            "success": False,
            "failure_reason": None,  # ❌ Falta este campo
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            LoginAttemptEvent(**invalid_data)

        assert "failure_reason es requerido cuando success=False" in str(exc_info.value)

    def test_login_event_serializes_to_dict_correctly(self):
        """
        Test: LoginAttemptEvent se serializa correctamente a diccionario

        Given: Un evento de login creado
        When: Se llama a to_dict()
        Then: Retorna un dict con todos los campos esperados
        """
        # Arrange
        event = LoginAttemptEvent(
            user_id="user-456",
            email="test@example.com",
            success=True,
            failure_reason=None,
            ip_address="10.0.0.1",
            user_agent="Safari/15.0",
        )

        # Act
        event_dict = event.to_dict()

        # Assert
        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == "LoginAttemptEvent"
        assert event_dict["user_id"] == "user-456"
        assert event_dict["email"] == "test@example.com"
        assert event_dict["success"] is True
        assert event_dict["failure_reason"] is None
        assert event_dict["severity"] == "MEDIUM"
        assert event_dict["ip_address"] == "10.0.0.1"
        assert event_dict["user_agent"] == "Safari/15.0"
        assert event_dict["aggregate_type"] == "Security"
        assert "event_id" in event_dict
        assert "occurred_on" in event_dict


class TestLogoutEvent:
    """Tests para LogoutEvent"""

    def test_logout_creates_event_with_low_severity(self):
        """
        Test: Logout crea evento con severity LOW

        Given: Datos válidos de logout
        When: Se crea un LogoutEvent
        Then: El evento se crea con severity LOW (acción normal)
        """
        # Arrange
        user_id = "user-789"
        ip_address = "192.168.1.100"
        user_agent = "Chrome/120.0"
        refresh_tokens_revoked = 2

        # Act
        event = LogoutEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_tokens_revoked=refresh_tokens_revoked,
        )

        # Assert
        assert event.user_id == user_id
        assert event.refresh_tokens_revoked == 2
        assert event.severity == SecuritySeverity.LOW  # Auto-ajustado
        assert event.aggregate_type == "Security"


class TestRefreshTokenUsedEvent:
    """Tests para RefreshTokenUsedEvent"""

    def test_refresh_token_used_creates_event_with_low_severity(self):
        """
        Test: Uso de refresh token crea evento con severity LOW

        Given: Datos válidos de uso de refresh token
        When: Se crea RefreshTokenUsedEvent
        Then: El evento se crea con severity LOW
        """
        # Arrange
        user_id = "user-999"
        refresh_token_id = "rt-abc123"
        ip_address = "192.168.1.50"
        user_agent = "Firefox/121.0"

        # Act
        event = RefreshTokenUsedEvent(
            user_id=user_id,
            refresh_token_id=refresh_token_id,
            new_access_token_created=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assert
        assert event.user_id == user_id
        assert event.refresh_token_id == refresh_token_id
        assert event.new_access_token_created is True
        assert event.severity == SecuritySeverity.LOW  # Auto-ajustado
        assert event.aggregate_type == "Security"

    def test_refresh_token_used_without_token_id_raises_error(self):
        """
        Test: RefreshTokenUsedEvent sin refresh_token_id lanza ValueError

        Given: Datos SIN refresh_token_id
        When: Se intenta crear el evento
        Then: Se lanza ValueError
        """
        # Arrange
        invalid_data = {
            "user_id": "user-123",
            "refresh_token_id": "",  # ❌ Vacío
            "new_access_token_created": True,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            RefreshTokenUsedEvent(**invalid_data)

        assert "refresh_token_id es requerido" in str(exc_info.value)


class TestRefreshTokenRevokedEvent:
    """Tests para RefreshTokenRevokedEvent - Severidad variable según reason"""

    def test_revocation_for_security_breach_has_critical_severity(self):
        """
        Test: Revocación por security_breach tiene severity CRITICAL

        Given: Datos de revocación por breach de seguridad
        When: Se crea RefreshTokenRevokedEvent con reason="security_breach"
        Then: El evento se crea con severity CRITICAL
        """
        # Arrange
        event = RefreshTokenRevokedEvent(
            user_id="user-compromised",
            ip_address="203.0.113.99",
            user_agent="Unknown",
            tokens_revoked_count=5,
            reason="security_breach",
        )

        # Assert
        assert event.reason == "security_breach"
        assert event.severity == SecuritySeverity.CRITICAL  # Auto-ajustado
        assert event.tokens_revoked_count == 5

    def test_revocation_for_password_change_has_high_severity(self):
        """
        Test: Revocación por password_change tiene severity HIGH

        Given: Datos de revocación por cambio de contraseña
        When: Se crea RefreshTokenRevokedEvent con reason="password_change"
        Then: El evento se crea con severity HIGH
        """
        # Arrange
        event = RefreshTokenRevokedEvent(
            user_id="user-pwd-change",
            ip_address="192.168.1.1",
            user_agent="Chrome/120.0",
            tokens_revoked_count=3,
            reason="password_change",
        )

        # Assert
        assert event.reason == "password_change"
        assert event.severity == SecuritySeverity.HIGH  # Auto-ajustado
        assert event.tokens_revoked_count == 3

    def test_revocation_for_logout_has_low_severity(self):
        """
        Test: Revocación por logout tiene severity LOW

        Given: Datos de revocación por logout normal
        When: Se crea RefreshTokenRevokedEvent con reason="logout"
        Then: El evento se crea con severity LOW
        """
        # Arrange
        event = RefreshTokenRevokedEvent(
            user_id="user-logout",
            ip_address="192.168.1.1",
            user_agent="Safari/15.0",
            tokens_revoked_count=1,
            reason="logout",
        )

        # Assert
        assert event.reason == "logout"
        assert event.severity == SecuritySeverity.LOW  # Auto-ajustado
        assert event.tokens_revoked_count == 1


class TestPasswordChangedEvent:
    """Tests para PasswordChangedEvent"""

    def test_password_changed_creates_event_with_high_severity(self):
        """
        Test: Cambio de contraseña crea evento con severity HIGH

        Given: Datos de cambio de contraseña
        When: Se crea PasswordChangedEvent
        Then: El evento se crea con severity HIGH
        """
        # Arrange
        event = PasswordChangedEvent(
            user_id="user-sec",
            ip_address="192.168.1.1",
            user_agent="Firefox/121.0",
            old_password_verified=True,
        )

        # Assert
        assert event.user_id == "user-sec"
        assert event.old_password_verified is True
        assert event.severity == SecuritySeverity.HIGH  # Auto-ajustado
        assert event.aggregate_type == "Security"


class TestEmailChangedEvent:
    """Tests para EmailChangedEvent"""

    def test_email_changed_creates_event_with_high_severity(self):
        """
        Test: Cambio de email crea evento con severity HIGH

        Given: Datos de cambio de email
        When: Se crea EmailChangedEvent
        Then: El evento se crea con severity HIGH
        """
        # Arrange
        event = EmailChangedEvent(
            user_id="user-email",
            ip_address="192.168.1.1",
            user_agent="Chrome/120.0",
            email_verification_required=True,
        )

        # Assert
        assert event.user_id == "user-email"
        assert event.email_verification_required is True
        assert event.severity == SecuritySeverity.HIGH  # Auto-ajustado
        assert event.aggregate_type == "Security"


class TestAccessDeniedEvent:
    """Tests para AccessDeniedEvent"""

    def test_access_denied_creates_event_with_high_severity(self):
        """
        Test: Acceso denegado crea evento con severity HIGH

        Given: Datos completos de acceso denegado
        When: Se crea AccessDeniedEvent
        Then: El evento se crea con severity HIGH
        """
        # Arrange
        event = AccessDeniedEvent(
            user_id="user-unauthorized",
            ip_address="192.168.1.200",
            user_agent="PostmanRuntime/7.0",
            resource_type="competition",
            resource_id="comp-456",
            action_attempted="delete",
            denial_reason="not_creator",
        )

        # Assert
        assert event.resource_type == "competition"
        assert event.resource_id == "comp-456"
        assert event.action_attempted == "delete"
        assert event.denial_reason == "not_creator"
        assert event.severity == SecuritySeverity.HIGH  # Auto-ajustado
        assert event.aggregate_type == "Security"


class TestRateLimitExceededEvent:
    """Tests para RateLimitExceededEvent"""

    def test_rate_limit_exceeded_creates_event_with_medium_severity(self):
        """
        Test: Rate limit excedido crea evento con severity MEDIUM

        Given: Datos de rate limiting activado
        When: Se crea RateLimitExceededEvent
        Then: El evento se crea con severity MEDIUM
        """
        # Arrange
        event = RateLimitExceededEvent(
            user_id="user-spammer",
            ip_address="203.0.113.100",
            user_agent="python-requests/2.28.0",
            endpoint="/api/v1/auth/login",
            limit_type="per_minute",
            limit_value="5/minute",
            request_count=10,
        )

        # Assert
        assert event.endpoint == "/api/v1/auth/login"
        assert event.limit_type == "per_minute"
        assert event.limit_value == "5/minute"
        assert event.request_count == 10
        assert event.severity == SecuritySeverity.MEDIUM  # Auto-ajustado
        assert event.aggregate_type == "Security"
