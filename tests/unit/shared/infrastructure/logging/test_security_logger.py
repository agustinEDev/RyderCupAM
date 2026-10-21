"""Tests unitarios para SecurityLogger"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from src.shared.domain.events.security_events import (
    LoginAttemptEvent,
    SecuritySeverity,
)
from src.shared.infrastructure.logging.security_logger import (
    SecurityLogger,
    get_security_logger,
)


@pytest.fixture
def temp_log_dir():
    """Directorio temporal para tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def logger(temp_log_dir):
    """SecurityLogger con directorio temporal"""
    return SecurityLogger(log_dir=temp_log_dir, log_file="test_security.log")


class TestSecurityLoggerSetup:
    """Tests de inicialización"""

    def test_logger_creates_log_file(self, logger, temp_log_dir):
        """Logger crea archivo de log"""
        log_file = temp_log_dir / "test_security.log"
        assert log_file.exists()

    def test_singleton_returns_same_instance(self):
        """get_security_logger() devuelve misma instancia"""
        logger1 = get_security_logger()
        logger2 = get_security_logger()
        assert logger1 is logger2


class TestSecurityLoggerWriting:
    """Tests de escritura de eventos"""

    def test_log_security_event_writes_to_file(self, logger, temp_log_dir):
        """log_security_event() escribe en archivo"""
        event = LoginAttemptEvent(
            user_id="user-123",
            email="test@example.com",
            success=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        logger.log_security_event(event)

        log_file = temp_log_dir / "test_security.log"
        content = log_file.read_text()
        assert "LoginAttemptEvent" in content
        assert "test@example.com" in content

    def test_log_writes_valid_json_format(self, logger, temp_log_dir):
        """Cada línea es JSON válido"""
        event = LoginAttemptEvent(
            user_id="user-456",
            email="json@test.com",
            success=False,
            failure_reason="Invalid credentials",
            ip_address="10.0.0.1",
            user_agent="Chrome/120.0",
        )

        logger.log_security_event(event)

        log_file = temp_log_dir / "test_security.log"
        lines = log_file.read_text().strip().split("\n")

        # Última línea debe ser JSON válido
        last_line = lines[-1]
        log_entry = json.loads(last_line)

        assert log_entry["extra"]["event_class"] == "LoginAttemptEvent"
        assert log_entry["extra"]["severity"] == "HIGH"

    def test_level_follows_outcome_not_severity(self, logger):
        """El nivel sale del resultado: un éxito HIGH va a INFO (BE #229)"""
        # Éxito → INFO aunque sea HIGH o CRITICAL
        assert logger._log_level(SecuritySeverity.HIGH, is_failure=False) == 20
        assert logger._log_level(SecuritySeverity.CRITICAL, is_failure=False) == 20
        # Fallo → HIGH/MEDIUM en WARNING (30), LOW en INFO (20)
        assert logger._log_level(SecuritySeverity.HIGH, is_failure=True) == 30
        assert logger._log_level(SecuritySeverity.MEDIUM, is_failure=True) == 30
        assert logger._log_level(SecuritySeverity.LOW, is_failure=True) == 20
        # Fallo CRITICAL → CRITICAL (50)
        assert logger._log_level(SecuritySeverity.CRITICAL, is_failure=True) == 50


class TestSecurityLoggerHelpers:
    """Tests de helper methods"""

    def test_log_login_attempt_helper(self, logger, temp_log_dir):
        """log_login_attempt() crea evento correctamente"""
        logger.log_login_attempt(
            user_id="user-789",
            email="helper@test.com",
            success=True,
            ip_address="192.168.1.100",
            user_agent="Safari/15.0",
        )

        log_file = temp_log_dir / "test_security.log"
        content = log_file.read_text()
        assert "helper@test.com" in content
        assert "LOGIN SUCCESS" in content

    def test_log_logout_helper(self, logger, temp_log_dir):
        """log_logout() crea evento correctamente"""
        logger.log_logout(
            user_id="user-999",
            ip_address="192.168.1.200",
            user_agent="Firefox/121.0",
            refresh_tokens_revoked=3,
        )

        log_file = temp_log_dir / "test_security.log"
        content = log_file.read_text()
        assert "LOGOUT" in content
        assert "user-999" in content


class TestSecurityLoggerEdgeCases:
    """Tests de casos edge"""

    def test_handles_anonymous_user(self, logger, temp_log_dir):
        """Maneja user_id=None (usuario anónimo)"""
        event = LoginAttemptEvent(
            user_id=None,  # Usuario anónimo
            email="anonymous@test.com",
            success=False,
            failure_reason="User not found",
            ip_address="203.0.113.1",
            user_agent="curl/7.68.0",
        )

        logger.log_security_event(event)

        log_file = temp_log_dir / "test_security.log"
        content = log_file.read_text()
        assert "Anonymous" in content or "null" in content


class TestTermsAccepted:
    """La aceptación de los Términos queda en el log de auditoría."""

    def test_log_terms_accepted_helper(self, logger, temp_log_dir):
        """
        Given: Un usuario que acepta los Términos
        When: Se registra con el helper
        Then: El log lleva el usuario, la versión, la IP y el tipo de evento
        """
        logger.log_terms_accepted(
            user_id="user-terms",
            ip_address="203.0.113.9",
            user_agent="Firefox/121.0",
            terms_version="2026-10-20",
        )

        content = (temp_log_dir / "test_security.log").read_text()
        assert "TERMS ACCEPTED" in content
        assert "user-terms" in content
        assert "2026-10-20" in content
        assert "TermsAcceptedEvent" in content

    def test_terms_accepted_event_is_low_severity(self):
        """
        Given: El evento de aceptación
        When: Se crea
        Then: Severidad LOW (acción normal) y su versión en el dict
        """
        from src.shared.domain.events.security_events import TermsAcceptedEvent

        event = TermsAcceptedEvent(
            user_id="u1",
            ip_address="203.0.113.9",
            user_agent="Firefox/121.0",
            terms_version="2026-10-20",
        )

        assert event.severity == SecuritySeverity.LOW
        assert event.to_dict()["terms_version"] == "2026-10-20"
