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
  S10 token de un dispositivo revocado → se borra, aunque otra cuenta de la cookie del
      navegador tenga una sesión más nueva (revocado o caducado, revisor de seguridad)
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

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
    caso = RefreshAccessTokenUseCase(
        uow, tokens, security_audit=SecurityAuditLogger(), aviso_de_cierre=AsyncMock()
    )
    return uow, usuario, dispositivo, viejo, caso


async def _nuevo(uow, usuario, device_id, despues=timedelta(seconds=5), dias=7, hace=None):
    nuevo = RefreshToken.create(
        user_id=usuario.id, token=NUEVO, device_id=device_id, expires_in_days=dias
    )
    nuevo._created_at = datetime.now() - hace if hace is not None else nuevo.created_at + despues
    await uow.refresh_tokens.save(nuevo)
    return nuevo


async def _rechazo(caso, jwt=VIEJO, navegador=()) -> RefreshRejectedError:
    with pytest.raises(RefreshRejectedError) as error:
        await caso.execute(
            RefreshAccessTokenRequestDTO(
                user_agent=IPHONE, dispositivos_del_navegador=list(navegador)
            ),
            jwt,
        )
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


# --- Tras el /code-review --------------------------------------------------------


async def test_s8_switching_account_in_the_same_browser_keeps_the_new_cookie():
    """
    Given: Ana cerró sesión y Bea entró en el mismo navegador (otro dispositivo: cada
           cuenta tiene el suyo); la cookie de dispositivo del navegador lleva los dos
    When: Llega tarde el refresco viejo de Ana
    Then: Se conserva la cookie: es la de Bea
    """
    uow, _ana, _dispositivo_de_ana, _viejo, caso = await _escena()
    bea = User.create(
        first_name="Bea",
        last_name="Ruiz",
        email_str="bea@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    await uow.users.save(bea)
    de_bea = UserDevice.create(bea.id, DeviceFingerprint.create(IPHONE, "203.0.113.7"))
    await uow.user_devices.save(de_bea)
    await _nuevo(uow, bea, de_bea.id)

    with pytest.raises(RefreshRejectedError) as error:
        await caso.execute(
            RefreshAccessTokenRequestDTO(
                user_agent=IPHONE, dispositivos_del_navegador=[str(de_bea.id.value)]
            ),
            VIEJO,
        )

    assert error.value.conserva_la_cookie is True


@pytest.mark.parametrize("como", ["desactivada", "dispositivo revocado", "inactiva"])
async def test_s9_only_a_replaced_token_keeps_the_cookie(como):
    """
    Given: Una sesión nueva y reciente en el dispositivo, y un rechazo que NO es de un
           token sustituido (cuenta desactivada, dispositivo revocado, 24 h sin uso)
    When: Refresca con el viejo
    Then: Se borra la cookie: «desactivada = sin sesión» no depende de la casualidad
    """
    from datetime import datetime

    uow, usuario, dispositivo, viejo, caso = await _escena()
    await _nuevo(uow, usuario, dispositivo.id)
    if como == "desactivada":
        usuario.deactivate(deactivated_by_user_id="5f0c8a2e-1b3d-4e6f-9a7b-2c4d6e8f0a1b")
        await uow.users.save(usuario)
    elif como == "dispositivo revocado":
        viejo._revoked = False
        await uow.refresh_tokens.save(viejo)
        dispositivo.revoke()
        await uow.user_devices.save(dispositivo)
    else:
        dispositivo._last_used_at = datetime.now() - timedelta(hours=25)
        await uow.user_devices.save(dispositivo)

    # Con la cookie de dispositivo del navegador, como manda uno de verdad
    navegador = [str(dispositivo.id.value)]
    assert (await _rechazo(caso, navegador=navegador)).conserva_la_cookie is False


async def _otra_cuenta_con_sesion_nueva(uow):
    otra = User.create(
        first_name="Luis",
        last_name="Gómez",
        email_str="luis@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    await uow.users.save(otra)
    suyo = UserDevice.create(otra.id, DeviceFingerprint.create(IPHONE, "203.0.113.7"))
    await uow.user_devices.save(suyo)
    await _nuevo(uow, otra, suyo.id)
    return suyo


@pytest.mark.parametrize("como", ["revocado", "caducado en la BD", "caducado en el JWT"])
async def test_s10_a_token_of_a_revoked_device_never_keeps_the_cookie(como):
    """
    Given: Un token de un dispositivo revocado y, en la cookie del navegador, otra cuenta
           con una sesión más nueva
    When: Refresca con él
    Then: Rechazado y se borra la cookie: un dispositivo revocado no se sustituye
    """
    uow, _usuario, dispositivo, viejo, caso = await _escena()
    dispositivo.revoke()
    await uow.user_devices.save(dispositivo)
    suyo = await _otra_cuenta_con_sesion_nueva(uow)
    if como != "revocado":
        viejo._revoked = False
        viejo._expires_at = datetime.now() - timedelta(minutes=1)
        await uow.refresh_tokens.save(viejo)
    if como == "caducado en el JWT":
        caso._token_service.verify_refresh_token.return_value = None
        caso._token_service.refresh_token_expired.return_value = True

    rechazo = await _rechazo(caso, navegador=[str(suyo.id.value)])

    assert rechazo.conserva_la_cookie is False


async def test_s10_the_same_scene_with_a_live_device_keeps_the_cookie():
    """
    Given: La misma escena, con el dispositivo del token activo
    When: Refresca con él
    Then: Conserva la cookie (el caso de cambio de cuenta, S8)
    """
    uow, _usuario, _dispositivo, _viejo, caso = await _escena()
    suyo = await _otra_cuenta_con_sesion_nueva(uow)

    rechazo = await _rechazo(caso, navegador=[str(suyo.id.value)])

    assert rechazo.conserva_la_cookie is True
