"""
Un rechazo de refresco tardío no borra la cookie de una sesión más nueva (BE #734).

Si llega tarde el 401 de una petición con la cookie vieja (otra pestaña, o una petición
en segundo plano) después de volver a entrar, su Set-Cookie borraría la cookie NUEVA.

  S1 rechazo y el dispositivo del token tiene una sesión más nueva y viva → se conserva
  S2 sin sesión más nueva → se borra, como hoy (también si la nueva está revocada,
     caducada o es de otro dispositivo)
  S3 token que no se identifica (no está en la BD) → se borra, como hoy
  Tras las revisiones (Agustín):
  S5 solo si la sesión nueva tiene menos de 5 minutos: la petición tardía llega segundos
     después; más vieja, se borra (sin cookies muertas de días)
  S6 también con el token ya caducado
  S7 si falla la consulta, se borra como siempre y el rechazo sigue siendo el mismo
"""

from datetime import datetime, timedelta
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


async def _nuevo(uow, usuario, device_id, despues=timedelta(seconds=5), dias=7, hace=None):
    nuevo = RefreshToken.create(
        user_id=usuario.id, token=NUEVO, device_id=device_id, expires_in_days=dias
    )
    nuevo._created_at = datetime.now() - hace if hace is not None else nuevo.created_at + despues
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


@pytest.mark.parametrize(
    ("hace", "conserva"), [(timedelta(minutes=4), True), (timedelta(minutes=6), False)]
)
async def test_s5_only_a_session_newer_than_five_minutes_keeps_the_cookie(hace, conserva):
    """
    Given: El token viejo (de hace una hora) y otro vivo en el mismo dispositivo
    When: Llega tarde el refresco con el viejo
    Then: Se conserva si el nuevo tiene menos de 5 minutos; si no, se borra
    """
    uow, usuario, dispositivo, viejo, caso = await _escena()
    viejo._created_at = datetime.now() - timedelta(hours=1)
    await uow.refresh_tokens.save(viejo)
    await _nuevo(uow, usuario, dispositivo.id, hace=hace)

    assert (await _rechazo(caso)).conserva_la_cookie is conserva


async def test_s6_an_expired_token_also_keeps_a_newer_sessions_cookie():
    """
    Given: Un token ya caducado (firma buena) y una sesión nueva y reciente en su dispositivo
    When: Llega tarde el refresco con el caducado
    Then: REFRESH_TOKEN_EXPIRED, pero conserva la cookie
    """
    from src.modules.user.application.use_cases.refresh_access_token_use_case import (
        RefreshRejection,
    )

    uow, usuario, dispositivo, _viejo, caso = await _escena()
    caso._token_service.verify_refresh_token.return_value = None
    caso._token_service.refresh_token_expired.return_value = True
    await _nuevo(uow, usuario, dispositivo.id)

    rechazo = await _rechazo(caso)

    assert rechazo.motivo is RefreshRejection.REFRESH_TOKEN_EXPIRED
    assert rechazo.conserva_la_cookie is True


async def test_s7_a_failing_check_deletes_as_always_and_keeps_the_rejection(monkeypatch, caplog):
    """
    Given: Un rechazo y la consulta de la sesión nueva fallando (BD con problemas)
    When: Llega el refresco
    Then: El mismo rechazo (no un 500) y se borra la cookie, como siempre (#750 punto 2)
    """
    import logging

    uow, usuario, dispositivo, _viejo, caso = await _escena()
    await _nuevo(uow, usuario, dispositivo.id)

    async def falla(*a, **k):
        raise RuntimeError("bd caída")

    monkeypatch.setattr(uow.refresh_tokens, "hay_uno_vivo_mas_nuevo", falla)

    with caplog.at_level(logging.ERROR):
        rechazo = await _rechazo(caso)

    assert rechazo.conserva_la_cookie is False
    assert "RuntimeError" in caplog.text
