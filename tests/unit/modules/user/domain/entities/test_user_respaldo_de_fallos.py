"""
El respaldo del bloqueo de la cuenta (BE #732).

Los fallos de cada red se frenan por su cuenta (correo + red). Este contador suma
los de todas las redes, contra un ataque repartido entre muchas: con 50 en una
hora, la cuenta se bloquea 30 minutos para los dispositivos desconocidos.

  #   caso                                                | esperado
  ----|----------------------------------------------------|---------------------------------
  R1  49 fallos dentro de la hora                           | sin bloquear
  R2  el fallo 50 dentro de la hora                         | bloqueada 30 min, con su evento
  R3  los fallos de hace más de una hora                    | no cuentan: la ventana vuelve a 0
  R4  el bloqueo, pasados 30 min                            | se acaba solo
  R5  el desbloqueo del administrador                       | limpia contador, ventana y bloqueo
  R6  el aviso de fallos                                    | se apunta su hora
"""

from datetime import datetime, timedelta

from src.modules.user.domain.entities.user import (
    FAILED_ATTEMPTS_WINDOW,
    LOCKOUT_DURATION_MINUTES,
    MAX_FAILED_ATTEMPTS,
    User,
)
from src.modules.user.domain.events.account_locked_event import AccountLockedEvent

LAS_DIEZ = datetime(2026, 11, 6, 10, 0)


def _usuario() -> User:
    return User.create(
        first_name="Ana",
        last_name="Pérez",
        email_str="ana@example.com",
        plain_password="ClaveSegura123!x",
    )


def _falla(user: User, veces: int, desde: datetime, cada: timedelta = timedelta(seconds=30)):
    for i in range(veces):
        user.record_failed_login(ahora=desde + cada * i)


def test_los_numeros_del_respaldo():
    """
    Given: El respaldo de BE #732
    When: Se leen sus constantes
    Then: 50 fallos en una hora, 30 minutos de bloqueo
    """
    assert MAX_FAILED_ATTEMPTS == 50
    assert timedelta(hours=1) == FAILED_ATTEMPTS_WINDOW
    assert LOCKOUT_DURATION_MINUTES == 30


def test_r1_49_fallos_dentro_de_la_hora_no_bloquean():
    """
    Given: Un usuario
    When: Falla 49 veces en 25 minutos
    Then: No está bloqueado
    """
    user = _usuario()
    _falla(user, 49, LAS_DIEZ)

    assert user.failed_login_attempts == 49
    assert not user.is_locked(ahora=LAS_DIEZ + timedelta(minutes=25))


def test_r2_el_fallo_50_bloquea_30_minutos():
    """
    Given: Un usuario con 49 fallos en la última hora
    When: Falla otra vez
    Then: Queda bloqueado 30 minutos desde ese fallo, y lo dice un evento
    """
    user = _usuario()
    _falla(user, 50, LAS_DIEZ)
    ultimo = LAS_DIEZ + timedelta(seconds=30) * 49

    assert user.locked_until == ultimo + timedelta(minutes=30)
    assert user.is_locked(ahora=ultimo + timedelta(minutes=29))
    assert any(isinstance(e, AccountLockedEvent) for e in user.get_domain_events())


def test_r3_los_fallos_de_hace_mas_de_una_hora_no_cuentan():
    """
    Given: 49 fallos a las 10:00
    When: Falla otra vez pasada la hora
    Then: La ventana empieza de nuevo: un fallo, sin bloqueo
    """
    user = _usuario()
    _falla(user, 49, LAS_DIEZ, cada=timedelta(seconds=1))
    user.record_failed_login(ahora=LAS_DIEZ + timedelta(hours=1, seconds=1))

    assert user.failed_login_attempts == 1
    assert user.locked_until is None


def test_r3b_justo_antes_de_la_hora_aun_cuenta():
    """
    Given: 49 fallos que empezaron a las 10:00
    When: El 50 llega a las 10:59:59
    Then: Bloquea: la ventana dura una hora entera
    """
    user = _usuario()
    _falla(user, 49, LAS_DIEZ, cada=timedelta(seconds=1))
    user.record_failed_login(ahora=LAS_DIEZ + timedelta(minutes=59, seconds=59))

    assert user.locked_until is not None


def test_r4_el_bloqueo_se_acaba_solo():
    """
    Given: Un usuario bloqueado por el respaldo
    When: Pasan 30 minutos
    Then: Ya no está bloqueado
    """
    user = _usuario()
    _falla(user, 50, LAS_DIEZ, cada=timedelta(seconds=0))

    assert user.is_locked(ahora=LAS_DIEZ + timedelta(minutes=29, seconds=59))
    assert not user.is_locked(ahora=LAS_DIEZ + timedelta(minutes=30))


def test_r5_el_desbloqueo_limpia_contador_ventana_y_bloqueo():
    """
    Given: Un usuario bloqueado por el respaldo
    When: Lo desbloquea un administrador
    Then: Contador a 0, sin bloqueo y sin ventana: el siguiente fallo empieza otra
    """
    user = _usuario()
    _falla(user, 50, LAS_DIEZ, cada=timedelta(seconds=0))
    user.unlock(unlocked_by_user_id="admin")

    assert user.failed_login_attempts == 0
    assert user.locked_until is None
    assert user.failed_login_window_started_at is None


def test_r6_el_aviso_de_fallos_apunta_su_hora():
    """
    Given: Un usuario sin avisos de fallos
    When: Se le apunta uno
    Then: Queda su hora, para el tope de uno por hora
    """
    user = _usuario()
    assert user.failed_login_notice_at is None

    user.apunta_el_aviso_de_fallos(LAS_DIEZ)

    assert user.failed_login_notice_at == LAS_DIEZ


def test_r3c_justo_a_la_hora_empieza_otra_ventana():
    """
    Given: 49 fallos que empezaron a las 10:00
    When: El siguiente llega a las 11:00 en punto
    Then: Ya es otra ventana: un fallo, sin bloqueo
    """
    user = _usuario()
    _falla(user, 49, LAS_DIEZ, cada=timedelta(seconds=1))
    user.record_failed_login(ahora=LAS_DIEZ + timedelta(hours=1))

    assert user.failed_login_attempts == 1
    assert user.locked_until is None
