"""
Un rechazo de refresco tardío no borra la cookie de una sesión más nueva (BE #734).

Si llega tarde el 401 de una petición con la cookie vieja (otra pestaña, o una petición
en segundo plano) después de volver a entrar, su Set-Cookie borraría la cookie NUEVA.

  S1 rechazo y el dispositivo del token tiene una sesión más nueva y viva → se conserva
  S2 sin sesión más nueva → se borra, como hoy (también si la nueva está revocada,
     caducada o es de otro dispositivo)
  S3 token que no se identifica (no está en la BD) → se borra, como hoy
"""

from datetime import timedelta
from unittest.mock import Mock

import pytest

from src.modules.user.application.dto.user_dto import RefreshAccessTokenRequestDTO
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
    RefreshRejectedError,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from tests.unit.modules.user.application.use_cases._sesion_al_registrar import (
    uow_con_sesion_al_registrar,
)

pytestmark = pytest.mark.asyncio

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) Version/18.1 Safari/604.1"
VIEJO = "refresco-viejo"
NUEVO = "refresco-nuevo"


async def _escena():
    uow = uow_con_sesion_al_registrar()
    usuario = User.create(
        first_name="Ana",
        last_name="Pérez",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    await uow.users.save(usuario)
    dispositivo = UserDevice.create(usuario.id, DeviceFingerprint.create(IPHONE, "203.0.113.7"))
    await uow.user_devices.save(dispositivo)
    viejo = RefreshToken.create(user_id=usuario.id, token=VIEJO, device_id=dispositivo.id)
    viejo.revoke()  # cerró sesión (o se revocó) y luego volvió a entrar
    await uow.refresh_tokens.save(viejo)
    tokens = Mock()
    tokens.verify_refresh_token.return_value = {"sub": str(usuario.id.value), "type": "refresh"}
    tokens.refresh_token_expired.return_value = False
    caso = RefreshAccessTokenUseCase(uow, tokens, security_audit=SecurityAuditLogger())
    return uow, usuario, dispositivo, viejo, caso


async def _nuevo(uow, usuario, device_id, despues=timedelta(seconds=5), dias=7):
    nuevo = RefreshToken.create(
        user_id=usuario.id, token=NUEVO, device_id=device_id, expires_in_days=dias
    )
    nuevo._created_at = nuevo.created_at + despues
    await uow.refresh_tokens.save(nuevo)
    return nuevo


async def _rechazo(caso, jwt=VIEJO) -> RefreshRejectedError:
    with pytest.raises(RefreshRejectedError) as error:
        await caso.execute(RefreshAccessTokenRequestDTO(user_agent=IPHONE), jwt)
    return error.value


async def test_s1_a_newer_live_session_on_the_device_keeps_the_cookie():
    """
    Given: El token viejo, revocado, y otro más nuevo y vivo en el mismo dispositivo
    When: Llega tarde el refresco con el viejo
    Then: Rechazado igual, pero conserva la cookie (la del navegador ya es la nueva)
    """
    uow, usuario, dispositivo, _viejo, caso = await _escena()
    await _nuevo(uow, usuario, dispositivo.id)

    assert (await _rechazo(caso)).conserva_la_cookie is True


async def test_s2_without_a_newer_session_the_cookie_is_deleted():
    """
    Given: Solo el token viejo, revocado
    When: Refresca con él
    Then: Rechazado y se borra la cookie, como hoy
    """
    _uow, _usuario, _dispositivo, _viejo, caso = await _escena()

    assert (await _rechazo(caso)).conserva_la_cookie is False


@pytest.mark.parametrize("como", ["revocada", "caducada", "de otro dispositivo", "más vieja"])
async def test_s2_only_a_newer_live_one_on_the_same_device_counts(como):
    """
    Given: Otra sesión que no cuenta (revocada, caducada, de otro dispositivo o anterior)
    When: Refresca con el viejo
    Then: Se borra la cookie
    """
    uow, usuario, dispositivo, _viejo, caso = await _escena()
    if como == "de otro dispositivo":
        otro = UserDevice.create(usuario.id, DeviceFingerprint.create("Mac", "198.51.100.1"))
        await uow.user_devices.save(otro)
        await _nuevo(uow, usuario, otro.id)
    elif como == "más vieja":
        await _nuevo(uow, usuario, dispositivo.id, despues=-timedelta(hours=1))
    elif como == "caducada":
        nuevo = await _nuevo(uow, usuario, dispositivo.id)
        nuevo._expires_at = nuevo.created_at - timedelta(minutes=1)
        await uow.refresh_tokens.save(nuevo)
    else:
        nuevo = await _nuevo(uow, usuario, dispositivo.id)
        nuevo.revoke()
        await uow.refresh_tokens.save(nuevo)

    assert (await _rechazo(caso)).conserva_la_cookie is False


async def test_s3_a_token_that_is_not_in_the_database_deletes_the_cookie():
    """
    Given: Un token que no está en la BD (no se sabe de qué dispositivo es)
    When: Refresca con él
    Then: Se borra la cookie, como hoy
    """
    uow, usuario, dispositivo, _viejo, caso = await _escena()
    await _nuevo(uow, usuario, dispositivo.id)

    assert (await _rechazo(caso, jwt="no-existe")).conserva_la_cookie is False
