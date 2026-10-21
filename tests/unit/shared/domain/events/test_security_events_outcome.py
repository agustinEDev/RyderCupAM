"""Tests del resultado (éxito o fallo) de los eventos de auditoría (BE #229).

La severidad dice cuánto importa un evento para la auditoría; `is_failure`,
si algo salió mal. Son ejes distintos: un cambio de contraseña es HIGH y no es
un fallo.
"""

import pytest

from src.shared.domain.events.security_events import (
    AccessDeniedEvent,
    EmailChangedEvent,
    LoginAttemptEvent,
    LogoutEvent,
    PasswordChangedEvent,
    PasswordResetCompletedAuditEvent,
    PasswordResetRequestedAuditEvent,
    RateLimitExceededEvent,
    RefreshTokenRevokedEvent,
    RefreshTokenUsedEvent,
    SecurityAuditEvent,
    SecuritySeverity,
    TermsAcceptedEvent,
)

_CTX = {"ip_address": "203.0.113.1", "user_agent": "pytest"}


def _casos() -> list[tuple[str, SecurityAuditEvent, bool, SecuritySeverity]]:
    """(id, evento, ¿fallo?, severidad que tiene hoy y no cambia)."""
    return [
        (
            "login_ok",
            LoginAttemptEvent(user_id="u1", email="a@b.es", success=True, **_CTX),
            False,
            SecuritySeverity.MEDIUM,
        ),
        (
            "login_ko",
            LoginAttemptEvent(
                user_id=None, email="a@b.es", success=False, failure_reason="x", **_CTX
            ),
            True,
            SecuritySeverity.HIGH,
        ),
        ("logout", LogoutEvent(user_id="u1", **_CTX), False, SecuritySeverity.LOW),
        (
            "terms",
            TermsAcceptedEvent(user_id="u1", terms_version="2026-10-20", **_CTX),
            False,
            SecuritySeverity.LOW,
        ),
        (
            "refresh_used",
            RefreshTokenUsedEvent(user_id="u1", refresh_token_id="t1", **_CTX),
            False,
            SecuritySeverity.LOW,
        ),
        (
            "revoked_logout",
            RefreshTokenRevokedEvent(user_id="u1", tokens_revoked_count=1, reason="logout", **_CTX),
            False,
            SecuritySeverity.LOW,
        ),
        (
            "revoked_idle",
            RefreshTokenRevokedEvent(user_id="u1", tokens_revoked_count=1, reason="idle", **_CTX),
            False,
            SecuritySeverity.LOW,
        ),
        (
            "revoked_password_change",
            RefreshTokenRevokedEvent(
                user_id="u1", tokens_revoked_count=2, reason="password_change", **_CTX
            ),
            False,
            SecuritySeverity.HIGH,
        ),
        (
            "revoked_security_breach",
            RefreshTokenRevokedEvent(
                user_id="u1", tokens_revoked_count=2, reason="security_breach", **_CTX
            ),
            True,
            SecuritySeverity.CRITICAL,
        ),
        (
            "password_changed",
            PasswordChangedEvent(user_id="u1", **_CTX),
            False,
            SecuritySeverity.HIGH,
        ),
        ("email_changed", EmailChangedEvent(user_id="u1", **_CTX), False, SecuritySeverity.HIGH),
        (
            "access_denied",
            AccessDeniedEvent(
                user_id="u1",
                resource_type="competition",
                action_attempted="update",
                denial_reason="not_creator",
                **_CTX,
            ),
            True,
            SecuritySeverity.HIGH,
        ),
        (
            "rate_limit",
            RateLimitExceededEvent(
                user_id=None,
                endpoint="/api/v1/auth/login",
                limit_type="per_minute",
                request_count=6,
                **_CTX,
            ),
            True,
            SecuritySeverity.MEDIUM,
        ),
        (
            "reset_requested_ok",
            PasswordResetRequestedAuditEvent(user_id="u1", email="a@b.es", success=True, **_CTX),
            False,
            SecuritySeverity.MEDIUM,
        ),
        (
            "reset_requested_ko",
            PasswordResetRequestedAuditEvent(
                user_id=None, email="a@b.es", success=False, failure_reason="x", **_CTX
            ),
            True,
            SecuritySeverity.HIGH,
        ),
        (
            "reset_completed_ok",
            PasswordResetCompletedAuditEvent(user_id="u1", email="a@b.es", success=True, **_CTX),
            False,
            SecuritySeverity.HIGH,
        ),
        (
            "reset_completed_ko",
            PasswordResetCompletedAuditEvent(
                user_id="u1", email="a@b.es", success=False, failure_reason="x", **_CTX
            ),
            True,
            SecuritySeverity.MEDIUM,
        ),
        (
            "reset_completed_ko_sin_usuario",
            PasswordResetCompletedAuditEvent(
                user_id=None, email="", success=False, failure_reason="x", **_CTX
            ),
            True,
            SecuritySeverity.MEDIUM,
        ),
    ]


CASOS = _casos()


@pytest.mark.parametrize(
    ("event", "fallo", "severidad"),
    [c[1:] for c in CASOS],
    ids=[c[0] for c in CASOS],
)
class TestResultadoDelEvento:
    def test_is_failure_matches_the_outcome(self, event, fallo, severidad):
        """
        Given: Un evento de auditoría con un resultado concreto
        When: Se consulta is_failure
        Then: Es True solo si algo salió mal
        """
        assert event.is_failure is fallo

    def test_severity_is_unchanged(self, event, fallo, severidad):
        """
        Given: El mismo evento
        When: Se consulta su severidad
        Then: Es la de siempre: el resultado no la toca
        """
        assert event.severity == severidad

    def test_is_failure_is_not_part_of_the_audit_record(self, event, fallo, severidad):
        """
        Given: El mismo evento
        When: Se serializa para el log de auditoría
        Then: El registro no gana campos nuevos
        """
        assert "is_failure" not in event.to_dict()
