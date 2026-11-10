"""
El evento del robo de un refresh token (F-02, caso A4).

  E1 es HIGH y un fallo de seguridad, con el dispositivo y cuántos tokens se revocaron
  E2 el helper del log escribe su línea (sin correo)
  E3 va a Sentry con su propio tope (uno por tipo cada 10 min): no comparte el de los
     cambios de contraseña
  E4 el adaptador del puerto lo manda al log compartido
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.modules.user.infrastructure.security import security_audit_logger as adaptador
from src.shared.domain.events.security_events import (
    PasswordChangedEvent,
    RefreshTokenReuseDetectedEvent,
    SecuritySeverity,
)
from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger

UA = "Mozilla/5.0"
IP = "203.0.113.7"


def _evento() -> RefreshTokenReuseDetectedEvent:
    return RefreshTokenReuseDetectedEvent(
        user_id="u-1", ip_address=IP, user_agent=UA, device_id="d-1", tokens_revoked_count=3
    )


def test_e1_it_is_a_high_security_failure():
    """
    Given: Un robo detectado
    Then: Severidad HIGH, cuenta como fallo y lleva el dispositivo y los revocados
    """
    evento = _evento()

    assert evento.severity is SecuritySeverity.HIGH
    assert evento.is_failure is True
    datos = evento.to_dict()
    assert datos["device_id"] == "d-1"
    assert datos["tokens_revoked_count"] == 3


def test_e1_a_negative_count_is_refused():
    with pytest.raises(ValueError):
        RefreshTokenReuseDetectedEvent(
            user_id="u-1", ip_address=IP, user_agent=UA, device_id="d-1", tokens_revoked_count=-1
        )


def test_e2_the_helper_writes_the_line():
    """
    Given: El log de seguridad
    When: Se registra el robo con el helper
    Then: La línea dice qué pasó, con el usuario, el dispositivo y la severidad HIGH
    """
    carpeta = Path(tempfile.mkdtemp())
    try:
        registro = SecurityLogger(log_dir=carpeta, log_file="robo.log")
        registro.log_refresh_token_reuse_detected(
            user_id="u-robo",
            ip_address=IP,
            user_agent=UA,
            device_id="d-robo",
            tokens_revoked_count=2,
        )
        registro.vacia()
        contenido = (carpeta / "robo.log").read_text()
    finally:
        shutil.rmtree(carpeta)

    assert "REFRESH TOKEN REUSE | User u-robo | device d-robo | 2 revoked" in contenido
    entrada = json.loads(contenido.strip().split("\n")[-1])
    assert entrada["extra"]["event_class"] == "RefreshTokenReuseDetectedEvent"
    assert entrada["extra"]["severity"] == "HIGH"


def test_e3_it_reaches_sentry_with_its_own_quota(monkeypatch):
    """
    Given: Un cambio de contraseña (HIGH) acaba de ir a Sentry
    When: Se detecta un robo, y luego otro antes de 10 minutos
    Then: El primero va (su tipo tiene su propio tope); el segundo, no
    """
    llamadas: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        modulo.sentry_sdk, "capture_message", lambda m, **k: llamadas.append((m, k))
    )
    monkeypatch.setattr(modulo, "_TOPE", modulo.TopeDeSentry(reloj=lambda: 1000.0))
    modulo.avisa_a_sentry(PasswordChangedEvent(user_id="u-1", ip_address=IP, user_agent=UA))

    modulo.avisa_a_sentry(_evento())
    modulo.avisa_a_sentry(_evento())

    assert [m for m, _ in llamadas] == [
        "Security event: PasswordChangedEvent",
        "Security event: RefreshTokenReuseDetectedEvent",
    ]
    assert llamadas[1][1]["level"] == "warning"


def test_e4_the_port_adapter_forwards_to_the_shared_log(monkeypatch):
    """
    Given: El adaptador del puerto de auditoría
    When: Registra el robo
    Then: Llega al log compartido con los mismos datos
    """
    compartido = Mock()
    monkeypatch.setattr(adaptador, "get_security_logger", lambda: compartido)

    adaptador.SecurityAuditLogger().log_refresh_token_reuse_detected(
        user_id="u-1", ip_address=IP, user_agent=UA, device_id="d-1", tokens_revoked_count=3
    )

    compartido.log_refresh_token_reuse_detected.assert_called_once_with(
        user_id="u-1", ip_address=IP, user_agent=UA, device_id="d-1", tokens_revoked_count=3
    )
