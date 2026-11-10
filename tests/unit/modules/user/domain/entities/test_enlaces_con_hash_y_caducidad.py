"""
Los enlaces de verificación y de restablecer, con hash y caducidad (fase 3, F-04/F-05/F-10).

  #   Caso                                         | Resultado
  ----|---------------------------------------------|------------------------------------
  C1  verificar dentro de las 48 h                 | verificada; el token ya no vale
  C1  verificar pasadas las 48 h                   | VerificationTokenExpiredError
                                                   |   (VERIFICATION_TOKEN_EXPIRED)
  C1  token que no es / sin caducidad (de antes)   | ValueError de enlace no válido, no
                                                   |   el de caducado
  C1  reenviar (set_verification_token)            | nuevo hash y otras 48 h
  C2  restablecer dentro de 1 h                    | vale; a la hora y un segundo, no
  C2  pedir otro                                   | el de antes deja de valer
  C2  usarlo dos veces                             | la segunda, InvalidResetTokenError
  C3  lo guardado                                  | el SHA-256 del token, nunca el token
  C3  guardado en claro (formato viejo)            | no vale: ni verifica ni restablece
  B2  aviso de registro                            | uno cada 24 h por cuenta
  H2  correos de restablecer                       | 10 por cuenta en 24 h; el 11.º no
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.domain.entities.user import (
    MAX_PASSWORD_RESET_EMAILS_PER_DAY,
    PASSWORD_RESET_TOKEN_LIFETIME,
    REGISTER_ATTEMPT_NOTICE_INTERVAL,
    VERIFICATION_TOKEN_LIFETIME,
    User,
)
from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.exceptions.verification_token_expired_error import (
    VerificationTokenExpiredError,
)
from src.modules.user.domain.value_objects.token_hash import hash_del_enlace

AHORA = datetime(2026, 11, 10, 10, 0)
NUEVA = "N3wS3cur3P@ss!"


def _sha(token: str) -> str:
    """El hash de un enlace, con el helper de producción (sin hashlib en los tests)."""
    return hash_del_enlace(token)


def _ana() -> User:
    return User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )


def test_the_lifetimes_are_the_approved_ones():
    """
    Given: Las duraciones de la tabla aprobada
    When: Se leen
    Then: 48 h la verificación, 1 h el restablecer, 24 h el aviso y 10 correos al día
    """
    assert timedelta(hours=48) == VERIFICATION_TOKEN_LIFETIME
    assert timedelta(hours=1) == PASSWORD_RESET_TOKEN_LIFETIME
    assert timedelta(hours=24) == REGISTER_ATTEMPT_NOTICE_INTERVAL
    assert MAX_PASSWORD_RESET_EMAILS_PER_DAY == 10


def test_c3_the_link_hash_is_sha256_in_hex():
    """
    Given: El helper con el que se guardan los enlaces
    When: Se aplica a un texto conocido
    Then: Da su SHA-256 en hexadecimal (valor fijo: los demás tests usan el helper)
    """
    assert hash_del_enlace("enlace-de-prueba") == (
        "284a19351629779d5e7974ab8eeb201b4278abceb46bfb7ef460aea2fa7b4bf7"
    )


# --- C1 / C3: verificación ------------------------------------------------------------


def test_c3_the_verification_token_is_stored_as_its_sha256():
    """
    Given: Una cuenta nueva
    When: Se genera su enlace de verificación
    Then: Se guarda el SHA-256 del token, nunca el token, y caduca a las 48 h
    """
    ana = _ana()

    token = ana.generate_verification_token(ahora=AHORA)

    assert ana.verification_token == _sha(token)
    assert ana.verification_token != token
    assert ana.verification_token_expires_at == AHORA + timedelta(hours=48)


def test_c1_verifying_within_48_hours_works_and_spends_the_token():
    """
    Given: Un enlace de verificación de hace 47 h 59 min
    When: Se usa
    Then: La cuenta queda verificada y el token, fuera
    """
    ana = _ana()
    token = ana.generate_verification_token(ahora=AHORA)

    assert ana.verify_email(token, ahora=AHORA + timedelta(hours=47, minutes=59)) is True

    assert ana.email_verified
    assert ana.verification_token is None
    assert ana.verification_token_expires_at is None


def test_c1_verifying_exactly_at_48_hours_still_works():
    """
    Given: Un enlace de verificación de hace justo 48 h
    When: Se usa
    Then: Vale (caduca DESPUÉS de las 48 h, como el cambio de correo)
    """
    ana = _ana()
    token = ana.generate_verification_token(ahora=AHORA)

    assert ana.verify_email(token, ahora=AHORA + timedelta(hours=48)) is True


def test_c1_an_expired_verification_link_says_so_with_its_code():
    """
    Given: Un enlace de verificación de hace 48 h y un segundo
    When: Se usa
    Then: VerificationTokenExpiredError (VERIFICATION_TOKEN_EXPIRED); la cuenta sigue
          sin verificar y el token guardado, para que vuelva a decir «caducado»
    """
    ana = _ana()
    token = ana.generate_verification_token(ahora=AHORA)

    with pytest.raises(VerificationTokenExpiredError) as error:
        ana.verify_email(token, ahora=AHORA + timedelta(hours=48, seconds=1))

    assert error.value.error_code == "VERIFICATION_TOKEN_EXPIRED"
    assert isinstance(error.value, ValueError)
    assert not ana.email_verified
    assert ana.verification_token == _sha(token)


def test_c1_a_wrong_token_is_invalid_not_expired():
    """
    Given: Un enlace vigente
    When: Se usa otro token
    Then: ValueError de enlace no válido, que NO es el de caducado
    """
    ana = _ana()
    ana.generate_verification_token(ahora=AHORA)

    with pytest.raises(ValueError) as error:
        ana.verify_email("otro-token-que-no-es", ahora=AHORA)

    assert not isinstance(error.value, VerificationTokenExpiredError)
    assert not ana.email_verified


def test_c3_a_plaintext_token_from_before_does_not_verify():
    """
    Given: Una cuenta con el token guardado en claro (formato de antes) y sin caducidad
    When: Se usa ese token
    Then: Enlace no válido (no «caducado»): el hash de ese token no es lo guardado
    """
    ana = _ana()
    ana._verification_token = "token-en-claro-de-antes-0123456789abcdef0123"
    ana._verification_token_expires_at = None

    with pytest.raises(ValueError) as error:
        ana.verify_email("token-en-claro-de-antes-0123456789abcdef0123", ahora=AHORA)

    assert not isinstance(error.value, VerificationTokenExpiredError)
    assert not ana.email_verified


def test_c1_a_hash_without_expiry_is_invalid():
    """
    Given: Un hash guardado pero sin fecha de caducidad (no debería pasar)
    When: Se usa su token
    Then: Enlace no válido: sin caducidad no se da por bueno
    """
    ana = _ana()
    token = ana.generate_verification_token(ahora=AHORA)
    ana._verification_token_expires_at = None

    with pytest.raises(ValueError) as error:
        ana.verify_email(token, ahora=AHORA)

    assert not isinstance(error.value, VerificationTokenExpiredError)


def test_c1_resending_stores_the_new_hash_and_another_48_hours():
    """
    Given: Un enlace de verificación ya caducado
    When: Se reenvía (set_verification_token con un token nuevo)
    Then: Se guarda el hash del nuevo con otras 48 h; el viejo ya no vale y el nuevo sí
    """
    ana = _ana()
    viejo = ana.generate_verification_token(ahora=AHORA)
    luego = AHORA + timedelta(days=3)

    ana.set_verification_token("token-nuevo-de-reenvio-0123456789abcdefghij", ahora=luego)

    assert ana.verification_token == _sha("token-nuevo-de-reenvio-0123456789abcdefghij")
    assert ana.verification_token_expires_at == luego + timedelta(hours=48)
    with pytest.raises(ValueError):
        ana.verify_email(viejo, ahora=luego)
    assert ana.verify_email("token-nuevo-de-reenvio-0123456789abcdefghij", ahora=luego)


def test_c1_confirming_ownership_by_another_path_clears_the_link():
    """
    Given: Un enlace de verificación pendiente
    When: El correo se demuestra por otro camino (Google, restablecer)
    Then: Ni token ni caducidad
    """
    ana = _ana()
    ana.generate_verification_token(ahora=AHORA)

    ana.confirm_email_ownership()

    assert ana.verification_token is None
    assert ana.verification_token_expires_at is None


# --- C2 / C3: restablecer -------------------------------------------------------------


def test_c3_the_reset_token_is_stored_as_its_sha256_for_one_hour():
    """
    Given: Una cuenta
    When: Pide restablecer la contraseña
    Then: Se guarda el SHA-256 del token y caduca a la hora
    """
    ana = _ana()

    token = ana.generate_password_reset_token(ahora=AHORA)

    assert ana.password_reset_token == _sha(token)
    assert ana.reset_token_expires_at == AHORA + timedelta(hours=1)


@pytest.mark.parametrize(
    ("pasado", "vale"),
    [
        (timedelta(minutes=59, seconds=59), True),
        (timedelta(hours=1), True),
        (timedelta(hours=1, seconds=1), False),
        (timedelta(hours=23), False),
    ],
)
def test_c2_the_reset_link_lasts_one_hour(pasado, vale):
    """
    Given: Un enlace de restablecer
    When: Se comprueba pasado un tiempo
    Then: Vale hasta la hora justa; después, no (antes valía 24 h)
    """
    ana = _ana()
    token = ana.generate_password_reset_token(ahora=AHORA)

    assert ana.can_reset_password(token, ahora=AHORA + pasado) is vale


def test_c2_asking_for_another_link_voids_the_previous_one():
    """
    Given: Un enlace de restablecer
    When: Se pide otro
    Then: El de antes ya no vale; el nuevo sí
    """
    ana = _ana()
    primero = ana.generate_password_reset_token(ahora=AHORA)

    segundo = ana.generate_password_reset_token(ahora=AHORA + timedelta(minutes=5))

    assert ana.can_reset_password(primero, ahora=AHORA + timedelta(minutes=6)) is False
    assert ana.can_reset_password(segundo, ahora=AHORA + timedelta(minutes=6)) is True


def test_c2_a_reset_link_is_used_once():
    """
    Given: Un enlace de restablecer ya usado
    When: Se usa otra vez
    Then: InvalidResetTokenError
    """
    ana = _ana()
    token = ana.generate_password_reset_token()
    ana.reset_password(token, NUEVA)

    with pytest.raises(InvalidResetTokenError):
        ana.reset_password(token, "Otr4S3cur3P@ss!")


def test_c2_an_expired_link_cannot_reset():
    """
    Given: Un enlace de restablecer de hace más de una hora
    When: Se usa
    Then: InvalidResetTokenError y la contraseña no cambia
    """
    ana = _ana()
    token = ana.generate_password_reset_token(ahora=datetime.now() - timedelta(hours=2))

    with pytest.raises(InvalidResetTokenError):
        ana.reset_password(token, NUEVA)

    assert ana.verify_password("SecureP@ssw0rd123!")


def test_c3_a_plaintext_reset_token_from_before_does_not_work():
    """
    Given: El token de restablecer guardado en claro (formato de antes), aún en plazo
    When: Se usa ese token
    Then: No vale
    """
    ana = _ana()
    ana._password_reset_token = "reset-en-claro-de-antes-0123456789abcdef012"
    ana._reset_token_expires_at = datetime.now() + timedelta(hours=10)

    assert ana.can_reset_password("reset-en-claro-de-antes-0123456789abcdef012") is False


# --- B2: el aviso al dueño, uno cada 24 h ---------------------------------------------


def test_b2_the_register_notice_is_reserved_once_every_24_hours():
    """
    Given: Una cuenta sin avisos de registro
    When: Se reserva el aviso tres veces: ahora, a las 23 h 59 y a las 24 h y un segundo
    Then: Sí, no, sí; y apunta cuándo
    """
    ana = _ana()

    assert ana.reserva_el_aviso_de_registro(AHORA) is True
    assert ana.register_attempt_notice_at == AHORA
    assert ana.reserva_el_aviso_de_registro(AHORA + timedelta(hours=23, minutes=59)) is False
    assert ana.register_attempt_notice_at == AHORA
    luego = AHORA + timedelta(hours=24, seconds=1)
    assert ana.reserva_el_aviso_de_registro(luego) is True
    assert ana.register_attempt_notice_at == luego


# --- H2: 10 correos de restablecer al día por cuenta ----------------------------------


def test_h2_ten_reset_emails_a_day_per_account():
    """
    Given: Una cuenta sin correos de restablecer
    When: Se piden 11 en el mismo día
    Then: Caben los 10 primeros; el 11.º no
    """
    ana = _ana()

    cupos = [
        ana.cuenta_un_correo_de_reset(AHORA + timedelta(minutes=i))
        for i in range(MAX_PASSWORD_RESET_EMAILS_PER_DAY + 1)
    ]

    assert cupos == [True] * 10 + [False]


def test_h2_the_day_starts_again_24_hours_after_the_first():
    """
    Given: Una cuenta que gastó sus 10 correos
    When: Pide otro 24 h y un segundo después del primero
    Then: Cabe: empieza otro día
    """
    ana = _ana()
    for i in range(10):
        ana.cuenta_un_correo_de_reset(AHORA + timedelta(minutes=i))

    assert ana.cuenta_un_correo_de_reset(AHORA + timedelta(hours=23, minutes=59)) is False
    assert ana.cuenta_un_correo_de_reset(AHORA + timedelta(hours=24, seconds=1)) is True
    assert ana.password_reset_emails_in_window == 1
