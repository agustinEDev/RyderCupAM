"""
El cupo de Sentry para los eventos de seguridad (revisión de la fase 2, decidido por
Agustín el 9 nov 2026).

  Q1 login fallido                        -> nunca a Sentry (solo el log)
  Q2 restablecer a un correo desconocido  -> nunca a Sentry (solo el log)
  Q3 restablecer a un correo conocido     -> MEDIUM: no va, como hasta ahora
  Q4 HIGH: el primero de su tipo va, con omitted_since_last=0
  Q5 HIGH del mismo tipo antes de 10 min  -> no va
  Q6 HIGH del mismo tipo a los 10 min     -> va, diciendo cuántos se omitieron
  Q7 HIGH de otro tipo                    -> su propio tope
  Q8 CRITICAL                             -> siempre, sin tope
  Q9 el tope es por proceso, con un reloj monotónico por defecto
"""

import time

import pytest

from src.shared.domain.events.security_events import (
    AdminRoleChangedAuditEvent,
    LoginAttemptEvent,
    PasswordChangedEvent,
    PasswordResetRequestedAuditEvent,
)
from src.shared.infrastructure.logging import security_logger as modulo

UA = "Mozilla/5.0"
IP = "203.0.113.7"


class Reloj:
    """Un reloj que avanza a mano."""

    def __init__(self) -> None:
        """Empieza en 1000 s."""
        self.ahora = 1000.0

    def __call__(self) -> float:
        """La hora de ahora."""
        return self.ahora


@pytest.fixture
def reloj():
    """El reloj del tope."""
    return Reloj()


@pytest.fixture
def enviados(monkeypatch, reloj):
    """Lo que se manda a Sentry, con un tope nuevo que usa el reloj de mano."""
    llamadas: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        modulo.sentry_sdk, "capture_message", lambda m, **k: llamadas.append((m, k))
    )
    monkeypatch.setattr(modulo, "_TOPE", modulo.TopeDeSentry(reloj=reloj))
    return llamadas


def _cambio_de_contrasena() -> PasswordChangedEvent:
    """Un HIGH cualquiera."""
    return PasswordChangedEvent(user_id="u-1", ip_address=IP, user_agent=UA)


def _omitidos(datos: dict) -> int:
    """Cuántos se omitieron antes de este, según lo que se mandó."""
    return datos["contexts"]["security_event"]["omitted_since_last"]


def test_q1_a_failed_login_never_goes_to_sentry(enviados):
    """
    Given: Un login fallido (HIGH)
    When: Se avisa a Sentry
    Then: No se manda: es el evento más frecuente, y se queda en el log
    """
    modulo.avisa_a_sentry(
        LoginAttemptEvent(
            user_id=None,
            email="x@example.com",
            success=False,
            failure_reason="Invalid credentials",
            ip_address=IP,
            user_agent=UA,
        )
    )

    assert enviados == []


def test_q2_a_reset_to_an_unknown_email_never_goes_to_sentry(enviados):
    """
    Given: Una petición de restablecer a un correo que no es de nadie (HIGH)
    When: Se avisa a Sentry
    Then: No se manda
    """
    modulo.avisa_a_sentry(
        PasswordResetRequestedAuditEvent(
            user_id=None,
            email="nadie@example.com",
            success=False,
            failure_reason="Email not found (not revealed to client)",
            ip_address=IP,
            user_agent=UA,
        )
    )

    assert enviados == []


def test_q3_a_reset_to_a_known_email_is_medium_and_does_not_go(enviados):
    """
    Given: Una petición de restablecer a un correo de una cuenta (MEDIUM)
    When: Se avisa a Sentry
    Then: No se manda, como hasta ahora
    """
    modulo.avisa_a_sentry(
        PasswordResetRequestedAuditEvent(
            user_id="u-1",
            email="si@example.com",
            success=True,
            ip_address=IP,
            user_agent=UA,
        )
    )

    assert enviados == []


def test_q4_q5_q6_one_high_per_type_every_10_minutes_with_the_omitted_count(enviados, reloj):
    """
    Given: El mismo HIGH repetido
    When: Llega uno, tres más en menos de 10 min y otro a los 10 min del primero
    Then: Van el primero (0 omitidos) y el de los 10 min (3 omitidos), nada más
    """
    modulo.avisa_a_sentry(_cambio_de_contrasena())
    for segundos in (1, 300, 599):
        reloj.ahora = 1000.0 + segundos
        modulo.avisa_a_sentry(_cambio_de_contrasena())
    reloj.ahora = 1000.0 + 600
    modulo.avisa_a_sentry(_cambio_de_contrasena())

    assert [_omitidos(datos) for _, datos in enviados] == [0, 3]


def test_q6_the_window_starts_again_after_each_one_sent(enviados, reloj):
    """
    Given: Un HIGH mandado a los 600 s
    When: Llega otro a los 1100 s (500 s después del último mandado)
    Then: No va: la ventana cuenta desde el último que salió
    """
    modulo.avisa_a_sentry(_cambio_de_contrasena())
    reloj.ahora += 600
    modulo.avisa_a_sentry(_cambio_de_contrasena())
    reloj.ahora += 500
    modulo.avisa_a_sentry(_cambio_de_contrasena())

    assert len(enviados) == 2


def test_q7_each_type_has_its_own_window(enviados):
    """
    Given: Un HIGH de un tipo ya mandado
    When: Llega a la vez un HIGH de otro tipo
    Then: También va
    """
    from src.shared.domain.events.security_events import EmailChangedEvent

    modulo.avisa_a_sentry(_cambio_de_contrasena())
    modulo.avisa_a_sentry(EmailChangedEvent(user_id="u-1", ip_address=IP, user_agent=UA))

    assert [m for m, _ in enviados] == [
        "Security event: PasswordChangedEvent",
        "Security event: EmailChangedEvent",
    ]


def test_q8_critical_always_goes(enviados):
    """
    Given: Tres CRITICAL del mismo tipo seguidos
    When: Se avisa a Sentry
    Then: Van los tres, como error
    """
    for _ in range(3):
        modulo.avisa_a_sentry(
            AdminRoleChangedAuditEvent(
                user_id="admin", ip_address=IP, user_agent=UA, target_user_id="u-1"
            )
        )

    assert [datos["level"] for _, datos in enviados] == ["error"] * 3


def test_q9_the_default_clock_is_monotonic():
    """
    Given: Un tope sin reloj inyectado
    When: Se mira su reloj
    Then: Es time.monotonic: un cambio de hora del sistema no abre ni cierra la ventana
    """
    assert modulo.TopeDeSentry()._reloj is time.monotonic
    assert modulo.TopeDeSentry.VENTANA_S == 600


def test_q6_the_omitted_count_starts_again_after_each_one_sent(enviados, reloj):
    """
    Given: Un HIGH con uno omitido en su primera ventana y ninguno en la segunda
    When: Salen el de los 600 s y el de los 1200 s
    Then: El primero dice 1 omitido y el segundo 0: la cuenta empieza de nuevo
    """
    modulo.avisa_a_sentry(_cambio_de_contrasena())
    reloj.ahora += 1
    modulo.avisa_a_sentry(_cambio_de_contrasena())
    reloj.ahora += 599
    modulo.avisa_a_sentry(_cambio_de_contrasena())
    reloj.ahora += 600
    modulo.avisa_a_sentry(_cambio_de_contrasena())

    assert [_omitidos(datos) for _, datos in enviados] == [0, 1, 0]
