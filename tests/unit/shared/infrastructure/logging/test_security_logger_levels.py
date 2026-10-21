"""Nivel de logging de cada evento de auditoría (BE #229).

Sentry convierte en issue todo lo que llega a ERROR. Un éxito sale en INFO sea
cual sea su severidad; un fallo, como mucho en WARNING (rastro, no issue), salvo
el CRITICAL, que sigue en CRITICAL.
"""

import logging

import pytest

from src.shared.domain.events.security_events import SecuritySeverity
from src.shared.infrastructure.logging.security_logger import SecurityLogger
from tests.unit.shared.domain.events.test_security_events_outcome import CASOS

_NIVEL_ESPERADO = {
    "login_ok": logging.INFO,
    "login_ko": logging.WARNING,
    "logout": logging.INFO,
    "terms": logging.INFO,
    "refresh_used": logging.INFO,
    "revoked_logout": logging.INFO,
    "revoked_idle": logging.INFO,
    "revoked_password_change": logging.INFO,
    "revoked_security_breach": logging.CRITICAL,
    "password_changed": logging.INFO,
    "email_changed": logging.INFO,
    "access_denied": logging.WARNING,
    "rate_limit": logging.WARNING,
    "reset_requested_ok": logging.INFO,
    "reset_requested_ko": logging.WARNING,
    "reset_completed_ok": logging.INFO,
    "reset_completed_ko": logging.WARNING,
    "reset_completed_ko_sin_usuario": logging.WARNING,
}


@pytest.fixture
def capturado(tmp_path, caplog):
    """SecurityLogger con el handler de caplog colgado de 'security.audit'.

    El logger no propaga a la raíz, así que caplog no lo vería por sí solo.
    """
    security_logger = SecurityLogger(log_dir=tmp_path, log_file="audit.log")
    audit = logging.getLogger("security.audit")
    audit.addHandler(caplog.handler)
    caplog.clear()
    yield security_logger, caplog
    audit.removeHandler(caplog.handler)


def test_every_case_has_an_expected_level():
    """Ningún caso de la tabla se queda sin nivel esperado."""
    assert {c[0] for c in CASOS} == set(_NIVEL_ESPERADO)


@pytest.mark.parametrize(("event", "fallo"), [c[1:3] for c in CASOS], ids=[c[0] for c in CASOS])
def test_event_is_logged_at_the_level_of_its_outcome(capturado, request, event, fallo):
    """
    Given: Un evento de auditoría (clase y resultado)
    When: Se registra
    Then: Sale con el nivel que le toca y conserva su severidad en el registro
    """
    security_logger, caplog = capturado
    caso = request.node.callspec.id

    security_logger.log_security_event(event)

    [record] = caplog.records
    assert record.name == "security.audit"
    assert record.levelno == _NIVEL_ESPERADO[caso]
    assert record.severity == event.severity.value


@pytest.mark.parametrize(
    "event", [c[1] for c in CASOS if not c[2]], ids=[c[0] for c in CASOS if not c[2]]
)
def test_success_never_reaches_error(capturado, event):
    """
    Given: Un evento que cuenta un éxito
    When: Se registra
    Then: No llega a ERROR, así que Sentry no abre un issue
    """
    security_logger, caplog = capturado

    security_logger.log_security_event(event)

    assert all(r.levelno < logging.ERROR for r in caplog.records)


@pytest.mark.parametrize(
    ("severity", "is_failure", "nivel"),
    [
        (SecuritySeverity.CRITICAL, False, logging.INFO),
        (SecuritySeverity.HIGH, False, logging.INFO),
        (SecuritySeverity.MEDIUM, False, logging.INFO),
        (SecuritySeverity.LOW, False, logging.INFO),
        (SecuritySeverity.CRITICAL, True, logging.CRITICAL),
        (SecuritySeverity.HIGH, True, logging.WARNING),
        (SecuritySeverity.MEDIUM, True, logging.WARNING),
        (SecuritySeverity.LOW, True, logging.INFO),
    ],
)
def test_level_mapping(severity, is_failure, nivel):
    """
    Given: Una severidad y un resultado
    When: Se traduce a nivel de logging
    Then: Éxito = INFO; fallo = CRITICAL→CRITICAL, HIGH/MEDIUM→WARNING, LOW→INFO
    """
    assert SecurityLogger._log_level(severity, is_failure=is_failure) == nivel
