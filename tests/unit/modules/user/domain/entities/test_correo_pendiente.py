"""
El cambio de correo no surte efecto hasta verificar la dirección nueva (#749, revisión).

Antes, cambiar el correo lo ponía ya en la cuenta, sin verificar: un error al
escribirlo, o un atacante con su propia cuenta, dejaban una cuenta «sin verificar» con
un correo ajeno, y eso se aprovechaba para quedarse cuentas.

  #   Caso                                   | Resultado
  ----|----------------------------------------|----------------------------------------
  E1  pedir el cambio                        | la cuenta sigue con el correo de antes (y
                                             |   verificada); el nuevo, pendiente 24 h
  E2  confirmar a tiempo con su token        | el correo pasa a ser el nuevo, verificado
  E3  confirmar pasadas las 24 h             | EmailChangeExpiredError y el pendiente fuera
  E5  pedir otro con uno pendiente           | lo sustituye; el token de antes ya no vale
  E6  anular                                 | sin pendiente; su token ya no vale
      token que no es                        | EmailChangeInvalidError, nada cambia
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions import (
    EmailChangeExpiredError,
    EmailChangeInvalidError,
)

AHORA = datetime(2026, 11, 7, 10, 0)


def _ana(verificada: bool = True) -> User:
    ana = User.create(
        first_name="Ana",
        last_name="Dueña",
        email_str="ana@gmail.com",
        plain_password="SecureP@ssw0rd123!",
    )
    if verificada:
        ana.confirm_email_ownership()
    return ana


def test_e1_asking_keeps_the_old_email_and_leaves_the_new_one_pending():
    """
    Given: Ana, verificada
    When: Pide cambiar el correo a ana@trabajo.com
    Then: Sigue con ana@gmail.com y verificada; el nuevo, pendiente 24 h, con su token
    """
    ana = _ana()

    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    assert str(ana.email.value) == "ana@gmail.com"
    assert ana.email_verified
    assert ana.pending_email_at(AHORA) == "ana@trabajo.com"
    assert ana.pending_email_token and len(token) >= 32
    assert ana.pending_email_expires_at == AHORA + timedelta(hours=24)


def test_e2_confirming_in_time_switches_the_email():
    """Con su token y a tiempo: el correo es el nuevo, verificado, y no queda pendiente."""
    ana = _ana()
    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    ana.confirm_email_change(token, ahora=AHORA + timedelta(hours=23))

    assert str(ana.email.value) == "ana@trabajo.com"
    assert ana.email_verified
    assert ana.pending_email_at(AHORA) is None
    assert ana.pending_email_token is None


def test_e2_confirming_drops_a_password_reset_asked_for_the_old_email():
    """Un «Olvidé mi contraseña» pedido para el correo de antes no vale tras el cambio."""
    ana = _ana()
    ana.generate_password_reset_token()
    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    ana.confirm_email_change(token, ahora=AHORA)

    assert ana.password_reset_token is None


def test_e2_an_unverified_account_ends_verified_with_the_new_email():
    """E8: una cuenta del alta sin verificar que confirma el nuevo queda verificada con él."""
    ana = _ana(verificada=False)
    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    assert not ana.email_verified
    ana.confirm_email_change(token, ahora=AHORA)

    assert str(ana.email.value) == "ana@trabajo.com"
    assert ana.email_verified


def test_e3_confirming_too_late_drops_the_pending_change():
    """
    Given: Un cambio pedido hace más de 24 horas
    When: Se confirma
    Then: EmailChangeExpiredError; la cuenta sigue con el correo de antes y sin pendiente
    """
    ana = _ana()
    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    with pytest.raises(EmailChangeExpiredError):
        ana.confirm_email_change(token, ahora=AHORA + timedelta(hours=24, seconds=1))

    assert str(ana.email.value) == "ana@gmail.com"
    assert ana.pending_email_token is None


def test_e3_an_expired_pending_email_is_not_shown():
    """Pasadas las 24 horas, el pendiente ya no se muestra."""
    ana = _ana()
    ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    assert ana.pending_email_at(AHORA + timedelta(hours=25)) is None


def test_e5_a_second_request_replaces_the_first():
    """Pedir otro sustituye al pendiente: el token de antes ya no vale."""
    ana = _ana()
    viejo = ana.request_email_change("ana@trabajo.com", ahora=AHORA)
    nuevo = ana.request_email_change("ana@casa.com", ahora=AHORA)

    with pytest.raises(EmailChangeInvalidError):
        ana.confirm_email_change(viejo, ahora=AHORA)
    ana.confirm_email_change(nuevo, ahora=AHORA)

    assert str(ana.email.value) == "ana@casa.com"


def test_e6_cancelling_leaves_nothing_pending():
    """Anular: sin pendiente, y su token ya no vale."""
    ana = _ana()
    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    ana.cancel_email_change()

    assert ana.pending_email_at(AHORA) is None
    with pytest.raises(EmailChangeInvalidError):
        ana.confirm_email_change(token, ahora=AHORA)
    assert str(ana.email.value) == "ana@gmail.com"


def test_a_wrong_token_changes_nothing():
    """Un token que no es el suyo: EmailChangeInvalidError y el pendiente sigue."""
    ana = _ana()
    ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    with pytest.raises(EmailChangeInvalidError):
        ana.confirm_email_change("otro-token", ahora=AHORA)

    assert ana.pending_email_at(AHORA) == "ana@trabajo.com"


def test_asking_for_the_same_email_is_refused():
    """Pedir el correo que ya tiene no tiene sentido: ValueError."""
    ana = _ana()

    with pytest.raises(ValueError):
        ana.request_email_change("ana@gmail.com", ahora=AHORA)


def test_a_claim_cancels_a_pending_email_change():
    """
    Given: Una cuenta sin verificar con un cambio de correo pendiente (quien la creó
           pidió llevársela a su dirección)
    When: El dueño del correo se la queda
    Then: Ya no hay pendiente: aquel enlace no puede llevársela después
    """
    ana = _ana(verificada=False)
    token = ana.request_email_change("atacante@example.com", ahora=AHORA)

    ana.claim_with_verified_oauth()

    assert ana.pending_email_token is None
    with pytest.raises(EmailChangeInvalidError):
        ana.confirm_email_change(token, ahora=AHORA)


def test_the_token_is_kept_hashed_not_in_clear():
    """El token se guarda con hash: quien lea la BD no puede confirmar el cambio."""
    ana = _ana()

    token = ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    assert ana.pending_email_token != token
    ana.confirm_email_change(token, ahora=AHORA)
    assert str(ana.email.value) == "ana@trabajo.com"


def test_a_non_ascii_token_is_just_invalid():
    """Un token con tildes es inválido, no un error (antes, compare_digest lanzaba)."""
    ana = _ana()
    ana.request_email_change("ana@trabajo.com", ahora=AHORA)

    with pytest.raises(EmailChangeInvalidError):
        ana.confirm_email_change("tokén", ahora=AHORA)
