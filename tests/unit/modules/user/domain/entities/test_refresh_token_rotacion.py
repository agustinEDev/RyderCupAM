"""
La rotación del refresh token en la entidad (F-02 de la auditoría).

  R1 sustituir crea el sucesor con el mismo usuario, dispositivo, caducidad absoluta
     (7 días desde el login, no se alarga) e inicio de la sesión (`created_at`)
  R2 el sustituido queda marcado (cuándo y por cuál), sin revocar ni borrar
  R3 el margen de 60 s desde la sustitución: dentro a los 60 s, fuera a los 61 s
  R4 un token vigente (también uno de antes de la rotación) no está sustituido
  R5 un token revocado no se puede sustituir
  R6 volver a sustituir (respuesta perdida) apunta al último sucesor y reinicia el margen
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.domain.entities.refresh_token import (
    MARGEN_DE_LA_SUSTITUCION,
    RefreshToken,
)
from src.modules.user.domain.value_objects.token_hash import TokenHash
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId

AHORA = datetime(2026, 11, 10, 12, 0, 0)


def _token(dias_restantes: float = 7) -> RefreshToken:
    token = RefreshToken.create(
        user_id=UserId.generate(), token="original", device_id=UserDeviceId.generate()
    )
    token._created_at = AHORA - timedelta(days=7 - dias_restantes)
    token._expires_at = AHORA + timedelta(days=dias_restantes)
    return token


def test_r1_the_successor_keeps_user_device_absolute_expiry_and_session_start():
    """
    Given: Un token al que le quedan 2 días
    When: Se sustituye
    Then: El sucesor es del mismo usuario y dispositivo, caduca a la vez y su sesión
          empezó cuando la del original; su hash es el del token nuevo
    """
    original = _token(dias_restantes=2)

    sucesor = original.sustituye("sucesor", AHORA)

    assert sucesor.id != original.id
    assert sucesor.user_id == original.user_id
    assert sucesor.device_id == original.device_id
    assert sucesor.expires_at == original.expires_at
    assert sucesor.created_at == original.created_at
    assert sucesor.token_hash == TokenHash.from_token("sucesor")
    assert not sucesor.revoked
    assert not sucesor.is_replaced


def test_r2_the_replaced_one_is_marked_not_revoked():
    """
    Given: Un token vigente
    When: Se sustituye
    Then: Queda marcado con la hora y el sucesor; no se revoca
    """
    original = _token()

    sucesor = original.sustituye("sucesor", AHORA)

    assert original.is_replaced
    assert original.replaced_at == AHORA
    assert original.replaced_by_id == sucesor.id
    assert not original.revoked


@pytest.mark.parametrize(
    ("segundos", "dentro"), [(0, True), (59, True), (60, True), (61, False), (3600, False)]
)
def test_r3_the_sixty_second_margin(segundos, dentro):
    """
    Given: Un token sustituido
    When: Se mira el margen `segundos` después
    Then: Dentro hasta los 60 s incluidos; fuera después
    """
    original = _token()
    original.sustituye("sucesor", AHORA)

    assert timedelta(seconds=60) == MARGEN_DE_LA_SUSTITUCION
    assert original.en_el_margen(AHORA + timedelta(seconds=segundos)) is dentro


def test_r4_a_current_token_is_not_replaced_nor_in_the_margin():
    """
    Given: Un token vigente (como los de antes de la rotación: sin datos de sustitución)
    Then: No está sustituido ni en el margen
    """
    token = _token()

    assert not token.is_replaced
    assert token.replaced_at is None
    assert token.replaced_by_id is None
    assert token.en_el_margen(AHORA) is False


def test_r5_a_revoked_token_cannot_be_replaced():
    """
    Given: Un token revocado
    When: Se intenta sustituir
    Then: ValueError, y sigue sin sustituir
    """
    token = _token()
    token.revoke()

    with pytest.raises(ValueError):
        token.sustituye("sucesor", AHORA)
    assert not token.is_replaced


def test_r6_replacing_again_points_to_the_last_successor():
    """
    Given: Un token sustituido hace 5 minutos (la respuesta se perdió)
    When: Se vuelve a sustituir
    Then: Apunta al último sucesor, con la hora nueva (el margen empieza otra vez)
    """
    original = _token()
    original.sustituye("primero", AHORA - timedelta(minutes=5))

    segundo = original.sustituye("segundo", AHORA)

    assert original.replaced_by_id == segundo.id
    assert original.replaced_at == AHORA
    assert original.en_el_margen(AHORA + timedelta(seconds=30))
