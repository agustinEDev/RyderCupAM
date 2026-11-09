"""El log de seguridad que sobrevive a un despliegue (F-05b, auditoría OWASP del 9 nov 2026).

En Render el fichero `logs/security_audit.log` se pierde en cada despliegue. Cada
evento sale además en una línea JSON por la salida estándar, que Render guarda, y los
HIGH y CRITICAL llegan a Sentry (warning y error) con el id del usuario y la IP como
único dato personal: nunca el correo, contraseñas ni tokens. Un fallo de Sentry no
rompe ni la petición ni el log.
"""

import json
import logging

import pytest

from src.config import sentry_config
from src.shared.domain.events.security_events import (
    LoginAttemptEvent,
    LogoutEvent,
    RefreshTokenRevokedEvent,
)
from src.shared.infrastructure.logging import security_logger as modulo
from src.shared.infrastructure.logging.security_logger import SecurityLogger

IP = "203.0.113.7"
USUARIO = "11111111-2222-3333-4444-555555555555"
CORREO = "jugador@example.com"
CAMPOS_SECRETOS = {"password", "token", "access_token", "refresh_token", "csrf_token", "secret"}


@pytest.fixture
def audit(tmp_path):
    """Un SecurityLogger con su fichero en una carpeta temporal."""
    return SecurityLogger(log_dir=tmp_path, log_file="audit.log")


@pytest.fixture
def enviados(monkeypatch):
    """Lo que se manda a Sentry, en vez de mandarlo."""
    llamadas: list[tuple[str, dict]] = []

    def _captura(mensaje, **kwargs):
        llamadas.append((mensaje, kwargs))

    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", _captura)
    return llamadas


def _fallo_de_login() -> LoginAttemptEvent:
    """Un login fallido: HIGH, y lleva el correo que se intentó."""
    return LoginAttemptEvent(
        user_id=USUARIO,
        email=CORREO,
        success=False,
        failure_reason="Invalid credentials",
        ip_address=IP,
        user_agent="Mozilla/5.0",
    )


def _lineas_json(salida: str) -> list[dict]:
    """Las líneas de la salida estándar que son eventos de seguridad."""
    lineas = [json.loads(linea) for linea in salida.splitlines() if linea.strip()]
    return [linea for linea in lineas if "security_event" in linea.get("extra", {})]


def test_every_event_goes_to_stdout_as_one_json_line(audit, capsys, enviados):
    """
    Given: Un SecurityLogger y un login fallido
    When: Se registra el evento
    Then: Sale UNA línea JSON en la salida estándar con el tipo de evento, el usuario
          y la IP, sin ningún campo de contraseña ni de token
    """
    capsys.readouterr()

    audit.log_security_event(_fallo_de_login())

    [linea] = _lineas_json(capsys.readouterr().out)
    evento = linea["extra"]["security_event"]
    assert evento["event_type"] == "LoginAttemptEvent"
    assert evento["user_id"] == USUARIO
    assert evento["ip_address"] == IP
    assert evento["severity"] == "HIGH"
    assert CAMPOS_SECRETOS.isdisjoint(evento)
    assert linea["logger"].startswith("security.audit")


def test_the_local_file_is_still_written(audit, tmp_path, enviados):
    """
    Given: Un SecurityLogger con su fichero
    When: Se registra un evento
    Then: El fichero local sigue recibiéndolo, como antes
    """
    audit.log_security_event(_fallo_de_login())

    contenido = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "LoginAttemptEvent" in contenido


def test_stdout_follows_the_current_stdout(tmp_path, capsys, enviados):
    """
    Given: Un SecurityLogger creado ANTES de que cambie la salida estándar (el singleton)
    When: Se registra un evento con otra salida estándar
    Then: Sale por la salida de ese momento, no por una vieja ya cerrada
    """
    viejo = SecurityLogger(log_dir=tmp_path, log_file="viejo.log")
    capsys.readouterr()

    viejo.log_security_event(_fallo_de_login())

    assert len(_lineas_json(capsys.readouterr().out)) == 1


def test_a_high_event_goes_to_sentry_as_a_warning_without_pii(audit, enviados):
    """
    Given: Un login fallido (HIGH), que lleva el correo
    When: Se registra
    Then: Llega a Sentry como warning, agrupado por tipo, con el usuario, sin la IP ni
          el correo ni nada fuera de la lista permitida
    """
    audit.log_security_event(_fallo_de_login())

    [(mensaje, datos)] = enviados
    assert datos["level"] == "warning"
    assert mensaje == "Security event: LoginAttemptEvent"
    assert datos["fingerprint"] == ["security-event", "LoginAttemptEvent"]
    assert datos["user"] == {"id": USUARIO}
    contexto = datos["contexts"]["security_event"]
    assert contexto["user_id"] == USUARIO
    # Sin IP: el id basta, y la IP se queda en el log (revisión de la fase 2)
    assert set(contexto) <= {"event_id", "event_type", "occurred_on", "severity", "user_id"}
    assert IP not in json.dumps(datos, default=str)
    assert CORREO not in json.dumps(datos, default=str)
    assert CORREO not in mensaje


def test_a_critical_event_goes_to_sentry_as_an_error(audit, enviados):
    """
    Given: Una revocación por brecha de seguridad (CRITICAL)
    When: Se registra
    Then: Llega a Sentry como error
    """
    audit.log_security_event(
        RefreshTokenRevokedEvent(
            user_id=USUARIO,
            ip_address=IP,
            user_agent="Mozilla/5.0",
            tokens_revoked_count=3,
            reason="security_breach",
        )
    )

    [(_, datos)] = enviados
    assert datos["level"] == "error"


def test_a_high_success_also_goes_to_sentry(audit, enviados):
    """
    Given: Una contraseña cambiada (HIGH, y un éxito)
    When: Se registra
    Then: Llega a Sentry: lo que cuenta es la severidad, no el resultado
    """
    audit.log_password_changed(user_id=USUARIO, ip_address=IP, user_agent="Mozilla/5.0")

    assert [datos["level"] for _, datos in enviados] == ["warning"]


def test_a_low_event_does_not_go_to_sentry(audit, enviados):
    """
    Given: Un logout (LOW)
    When: Se registra
    Then: No llega a Sentry
    """
    audit.log_security_event(LogoutEvent(user_id=USUARIO, ip_address=IP, user_agent="Mozilla/5.0"))

    assert enviados == []


def test_a_target_user_id_reaches_sentry(audit, enviados):
    """
    Given: Un evento de administrador con la cuenta afectada (`*_user_id`)
    When: Se registra
    Then: El id de la cuenta afectada llega a Sentry: también es un id de usuario
    """
    audit.log_account_deactivated(
        user_id=USUARIO,
        deactivated_user_id="otra-cuenta",
        devices_revoked=1,
        tokens_revoked=1,
        ip_address=IP,
    )

    [(_, datos)] = enviados
    assert datos["contexts"]["security_event"]["deactivated_user_id"] == "otra-cuenta"


def test_a_sentry_failure_does_not_break_the_log(audit, tmp_path, capsys, monkeypatch):
    """
    Given: Sentry lanzando una excepción al mandar
    When: Se registra un evento HIGH
    Then: No sale ninguna excepción y el evento queda en el fichero y en la salida estándar
    """

    def _revienta(*_args, **_kwargs):
        raise RuntimeError("sentry caído")

    monkeypatch.setattr(modulo.sentry_sdk, "capture_message", _revienta)
    capsys.readouterr()

    audit.log_security_event(_fallo_de_login())

    assert "LoginAttemptEvent" in (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert len(_lineas_json(capsys.readouterr().out)) == 1


def test_sentry_ignores_the_audit_loggers_so_nothing_goes_twice(monkeypatch):
    """
    Given: Sentry configurado (con su integración de logging)
    When: Se inicia
    Then: Ignora los loggers de auditoría (`security.audit` y los de otro fichero): el
          evento ya va a Sentry filtrado, y por la integración saldría entero (correo
          incluido, en las migas de pan) y el CRITICAL dos veces
    """
    from unittest.mock import patch

    from sentry_sdk.integrations import logging as integracion

    monkeypatch.setattr(
        sentry_config.settings, "SENTRY_DSN", "https://public@o0.ingest.sentry.io/0"
    )
    monkeypatch.setattr(integracion, "_IGNORED_LOGGERS", set(integracion._IGNORED_LOGGERS))
    with patch.object(sentry_config.sentry_sdk, "init"):
        sentry_config.init_sentry()

    handler = integracion.EventHandler()
    for nombre in ("security.audit", "security.audit.0123456789ab"):
        registro = logging.LogRecord(nombre, logging.CRITICAL, __file__, 1, "x", None, None)
        assert not handler._can_record(registro)
    otro = logging.LogRecord("src.otro", logging.ERROR, __file__, 1, "x", None, None)
    assert handler._can_record(otro)
