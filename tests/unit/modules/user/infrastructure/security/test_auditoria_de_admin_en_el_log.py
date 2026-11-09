"""
Lo que el adaptador del log de seguridad escribe por cada acción de administrador
(F-20, auditoría OWASP del 9 nov 2026): un evento CRITICAL con el administrador, la
cuenta afectada y la IP, sin correos.
"""

import pytest

from src.modules.user.infrastructure.security import security_audit_logger as adaptador
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger

ADMIN = "admin-0000"
CUENTA = "cuenta-1111"
IP = "203.0.113.9"


@pytest.fixture
def registros(tmp_path, caplog, monkeypatch):
    """Los registros del log de seguridad (en una carpeta temporal), sin mandar a Sentry."""
    audit = SecurityLogger(log_dir=tmp_path, log_file="audit.log")
    monkeypatch.setattr(adaptador, "get_security_logger", lambda: audit)
    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", lambda *_a, **_k: None)
    audit._logger.addHandler(caplog.handler)
    caplog.clear()
    yield caplog
    audit._logger.removeHandler(caplog.handler)


def _evento(registros) -> dict:
    """El único evento de seguridad registrado (de caplog, que se renueva en cada fase)."""
    [registro] = registros.records
    return registro.security_event


def test_the_admin_role_change_is_a_critical_event(registros):
    """
    Given: El adaptador del log de seguridad
    When: Se apunta que un administrador dio el rol a una cuenta
    Then: Evento CRITICAL con el administrador, la cuenta, el rol nuevo y la IP
    """
    SecurityAuditLogger().log_admin_role_changed(
        user_id=ADMIN, target_user_id=CUENTA, is_admin=True, ip_address=IP, user_agent="UA"
    )

    evento = _evento(registros)
    assert evento["event_type"] == "AdminRoleChangedAuditEvent"
    assert evento["severity"] == "CRITICAL"
    assert (evento["user_id"], evento["target_user_id"]) == (ADMIN, CUENTA)
    assert (evento["is_admin"], evento["ip_address"]) == (True, IP)


def test_the_account_deletion_is_a_critical_event(registros):
    """
    Given: El adaptador del log de seguridad
    When: Se apunta que un administrador borró una cuenta
    Then: Evento CRITICAL con el administrador, la cuenta borrada y la IP
    """
    SecurityAuditLogger().log_account_deleted_by_admin(
        user_id=ADMIN, deleted_user_id=CUENTA, ip_address=IP, user_agent="UA"
    )

    evento = _evento(registros)
    assert evento["event_type"] == "AccountDeletedByAdminAuditEvent"
    assert evento["severity"] == "CRITICAL"
    assert (evento["user_id"], evento["deleted_user_id"], evento["ip_address"]) == (
        ADMIN,
        CUENTA,
        IP,
    )


def test_the_admin_email_change_is_a_critical_event_without_emails(registros):
    """
    Given: El adaptador del log de seguridad
    When: Se apunta que un administrador pidió otro correo para una cuenta
    Then: Evento CRITICAL con el administrador, la cuenta y la IP, sin ningún correo
    """
    SecurityAuditLogger().log_admin_email_change_requested(
        user_id=ADMIN, target_user_id=CUENTA, ip_address=IP, user_agent="UA"
    )

    evento = _evento(registros)
    assert evento["event_type"] == "AdminEmailChangeRequestedAuditEvent"
    assert evento["severity"] == "CRITICAL"
    assert (evento["user_id"], evento["target_user_id"], evento["ip_address"]) == (
        ADMIN,
        CUENTA,
        IP,
    )
    assert not any("email" in clave for clave in evento)
