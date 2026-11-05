"""
El correo de «nuevo inicio de sesión», al propio usuario (BE #737, fase 4).

  #   caso                                                     | ¿correo?
  ----|-------------------------------------------------------|-------------------------------
  N1  entra desde un dispositivo nuevo y ya tenía otros        | sí: tipo, navegador, hora de
                                                               |   España, país y enlace
  N2  es su primer dispositivo (acaba de registrarse)          | no
  N3  entra desde un dispositivo que ya conocemos              | no
  N4  otro dispositivo nuevo hace menos de una hora            | no: como mucho uno por hora
  N5  falla el envío                                           | el login sigue; no lanza
  N6  la app instalada                                         | «iPhone · app instalada»
  N7  sin país                                                 | el correo no lo menciona
  N8  se registró hace 5 minutos y entra desde otro dispositivo | sí: el primero no avisó
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    AvisoDeNuevoInicioDeSesion,
)
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.domain.entities.country import Country
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"
# 5 nov 2026, 19:07 UTC = 20:07 en la península
AHORA = datetime(2026, 11, 5, 19, 7)


class _Paises:
    async def find_by_code(self, code: CountryCode):
        if code.value == "ES":
            return Country(code=CountryCode("ES"), name_en="Spain", name_es="España")
        return None


def _dispositivo(user_id, ua, creado_hace=timedelta(days=10), instalada=False, pais=None):
    d = UserDevice.create(
        user_id,
        DeviceFingerprint.create(ua, "203.0.113.7", installed_app=instalada),
        installed_app=instalada,
        country_code=pais,
    )
    d._created_at = AHORA - creado_hace
    d._last_used_at = d._created_at
    return d


async def _escena(*dispositivos):
    uow = InMemoryUnitOfWork()
    for d in dispositivos:
        await uow.user_devices.save(d)
    correo = AsyncMock()
    correo.send_new_login_notification.return_value = True
    return uow, correo, AvisoDeNuevoInicioDeSesion(uow, correo, _Paises(), reloj=lambda: AHORA)


async def test_n1_new_device_when_user_had_others_sends_the_notice():
    """
    Given: Un usuario con un Mac de hace 10 días
    When: Entra desde un iPhone nuevo, en España
    Then: Le llega un correo con «iPhone · Safari», la hora de España (20:07) y «España»
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0), pais="ES")
    _, correo, aviso = await _escena(mac, iphone)

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_awaited_once()
    kwargs = correo.send_new_login_notification.await_args.kwargs
    assert kwargs["to_email"] == "ana@example.com"
    assert kwargs["dispositivo"] == "iPhone · Safari"
    assert "20:07" in kwargs["cuando"] and "5 nov 2026" in kwargs["cuando"]
    assert kwargs["pais"] == "España"


async def test_n2_first_device_after_registering_sends_nothing():
    """
    Given: Un usuario sin ningún otro dispositivo
    When: Entra con el primero
    Then: No hay correo: acaba de registrarse
    """
    usuario = UserId(uuid4())
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(iphone)

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_not_awaited()


async def test_n3_known_device_sends_nothing():
    """
    Given: Un dispositivo que ya conocíamos
    When: Entra con él
    Then: No hay correo
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE)
    _, correo, aviso = await _escena(mac, iphone)

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(iphone.id.value), es_nuevo=False)

    correo.send_new_login_notification.assert_not_awaited()


async def test_n4_another_new_device_in_the_last_hour_sends_nothing():
    """
    Given: Un Mac viejo y un iPad dado de alta hace 20 minutos
    When: Entra desde un iPhone nuevo
    Then: No hay correo: como mucho uno por hora
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    ipad = _dispositivo(
        usuario,
        IPHONE.replace("iPhone; CPU iPhone OS", "iPad; CPU OS"),
        creado_hace=timedelta(minutes=20),
    )
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, ipad, iphone)

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_not_awaited()


async def test_n5_a_failing_email_does_not_raise():
    """
    Given: El envío del correo lanza
    When: Se avisa
    Then: No sube: el login sigue
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, iphone)
    correo.send_new_login_notification.side_effect = RuntimeError("Mailgun caído")

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(iphone.id.value), es_nuevo=True)


async def test_n6_n7_installed_app_label_and_no_country():
    """
    Given: Un iPhone con la app instalada, sin país
    When: Se avisa
    Then: «iPhone · app instalada» y sin país
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    app = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0), instalada=True)
    _, correo, aviso = await _escena(mac, app)

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(app.id.value), es_nuevo=True)

    kwargs = correo.send_new_login_notification.await_args.kwargs
    assert kwargs["dispositivo"] == "iPhone · app instalada"
    assert kwargs["pais"] is None


async def test_n8_just_registered_and_a_second_device_sends_the_notice():
    """
    Given: Un usuario que se registró hace 5 minutos con su Mac
    When: Entra desde un iPhone nuevo
    Then: Le llega el aviso: el Mac fue el primero y no avisó, así que no cuenta para el «uno por hora»
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC, creado_hace=timedelta(minutes=5))
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, iphone)

    await aviso.avisa(usuario, "ana@example.com", "Ana", str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_awaited_once()
