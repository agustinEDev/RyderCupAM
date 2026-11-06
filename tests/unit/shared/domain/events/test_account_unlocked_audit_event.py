"""El evento de auditoría del desbloqueo manual (hotfix 2.50.1)."""

from src.shared.domain.events.security_events import (
    AccountUnlockedAuditEvent,
    SecuritySeverity,
)
from src.shared.infrastructure.logging.security_logger import SecurityLogger


def _evento():
    return AccountUnlockedAuditEvent(
        user_id="admin-1",
        ip_address="203.0.113.7",
        user_agent="Mozilla/5.0",
        unlocked_user_id="ana-1",
        previous_failed_attempts=10,
    )


def test_quitar_un_bloqueo_es_de_severidad_alta_y_lleva_a_quien():
    """
    Given: Un desbloqueo manual
    When: Se serializa para el log
    Then: Severidad HIGH, y lleva al administrador, la cuenta y los fallos
    """
    d = _evento().to_dict()

    assert d["severity"] == SecuritySeverity.HIGH.value
    assert (d["user_id"], d["unlocked_user_id"], d["previous_failed_attempts"]) == (
        "admin-1",
        "ana-1",
        10,
    )


def test_el_mensaje_del_log_dice_quien_desbloqueo_a_quien():
    """
    Given: El logger de seguridad
    When: Formatea un desbloqueo manual
    Then: El mensaje dice que se desbloqueó, quién lo hizo y a qué cuenta
    """
    mensaje = SecurityLogger()._build_message(_evento())

    assert "ACCOUNT UNLOCKED" in mensaje
    assert "admin-1" in mensaje and "ana-1" in mensaje
