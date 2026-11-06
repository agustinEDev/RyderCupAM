"""
El correo de «nuevo inicio de sesión», al propio usuario (BE #737, fase 4).

  #   caso                                                     | ¿correo?
  ----|-------------------------------------------------------|-------------------------------
  N1  entra desde un dispositivo desconocido y ya tenía otros  | sí: tipo, navegador, hora de
                                                               |   España, país y enlace
  N2  es su único dispositivo (p. ej. tras la limpieza)        | sí: también puede ser un intruso
  N3  entra con la cookie de un dispositivo que ya conocemos   | no
  N3b entra SIN cookie y la huella lo reconoce                 | sí: puede ser otro con el mismo
                                                               |   móvil y la misma red
  N4  este dispositivo avisó hace menos de una hora            | no: uno por dispositivo y hora
  N4b otro dispositivo avisó hace 20 min                       | sí: el aviso de uno no tapa el
                                                               |   de otro
  N5  falla el envío                                           | el login sigue; no lanza, y no
                                                               |   queda apuntado como enviado
  N6  la app instalada                                         | «iPhone · app instalada»
  N7  sin país                                                 | el correo no lo menciona
  N8  se registró hace 5 minutos y entra desde otro dispositivo | sí
  N9  su correo aún no está confirmado                         | no: solo le llega el de confirmar
  N10 el alta con Google                                       | no: acaba de crear la cuenta
  N11 tras avisar                                              | el dispositivo queda apuntado
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.device_dto import AvisoDeNuevoInicioRequestDTO
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


def _dispositivo(
    user_id, ua, creado_hace=timedelta(days=10), instalada=False, pais=None, avisado_hace=None
):
    d = UserDevice.create(
        user_id,
        DeviceFingerprint.create(ua, "203.0.113.7", installed_app=instalada),
        installed_app=instalada,
        country_code=pais,
    )
    d._created_at = AHORA - creado_hace
    d._last_used_at = d._created_at
    if avisado_hace is not None:
        d.apunta_el_aviso(AHORA - avisado_hace)
    return d


async def _avisa(aviso, usuario, device_id, es_nuevo=True, verificado=True, es_alta=False):
    await aviso.avisa(
        AvisoDeNuevoInicioRequestDTO(
            user_id=str(usuario.value),
            email="ana@example.com",
            nombre="Ana",
            device_id=device_id,
            desconocido=es_nuevo,
            verificado=verificado,
            es_alta=es_alta,
        )
    )


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

    await _avisa(aviso, usuario, str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_awaited_once()
    kwargs = correo.send_new_login_notification.await_args.kwargs
    assert kwargs["to_email"] == "ana@example.com"
    assert kwargs["dispositivo"] == "iPhone · Safari"
    assert "20:07" in kwargs["cuando"] and "5 nov 2026" in kwargs["cuando"]
    assert kwargs["pais"] == "España"


async def test_n2_only_device_sends_the_notice():
    """
    Given: Un usuario sin ningún otro dispositivo (la limpieza borró los de hace 30 días)
    When: Entra con uno nuevo
    Then: Le llega el aviso: también puede ser un intruso
    """
    usuario = UserId(uuid4())
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(iphone)

    await _avisa(aviso, usuario, str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_awaited_once()


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

    await _avisa(aviso, usuario, str(iphone.id.value), es_nuevo=False)

    correo.send_new_login_notification.assert_not_awaited()


async def test_n4_this_device_notified_in_the_last_hour_sends_nothing():
    """
    Given: Un iPhone desconocido que ya avisó hace 20 minutos
    When: Vuelve a entrar sin cookie
    Then: No hay correo: como mucho uno por dispositivo y hora
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, avisado_hace=timedelta(minutes=20))
    _, correo, aviso = await _escena(mac, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value))

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

    await _avisa(aviso, usuario, str(iphone.id.value), es_nuevo=True)

    assert iphone.aviso_enviado_at is None


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

    await _avisa(aviso, usuario, str(app.id.value), es_nuevo=True)

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

    await _avisa(aviso, usuario, str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_awaited_once()


async def test_n4b_another_device_notice_does_not_hide_this_one():
    """
    Given: Un iPad que avisó hace 20 minutos (por ejemplo, tu portátil nuevo)
    When: Entra desde un iPhone desconocido
    Then: Le llega el aviso: el de un dispositivo no tapa el de otro
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    ipad = _dispositivo(
        usuario,
        IPHONE.replace("iPhone; CPU iPhone OS", "iPad; CPU OS"),
        creado_hace=timedelta(minutes=20),
        avisado_hace=timedelta(minutes=20),
    )
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, ipad, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value))

    correo.send_new_login_notification.assert_awaited_once()


async def test_n3b_a_device_recognized_only_by_fingerprint_notifies():
    """
    Given: Un iPhone conocido de hace 10 días, sin aviso reciente
    When: Entra sin su cookie y la huella lo reconoce (desconocido=True)
    Then: Le llega el aviso: puede ser otro con el mismo móvil y la misma red
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE)
    _, correo, aviso = await _escena(mac, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value), es_nuevo=True)

    correo.send_new_login_notification.assert_awaited_once()


async def test_n4c_a_notice_older_than_an_hour_does_not_stop_a_new_one():
    """
    Given: Un iPad que avisó hace 61 minutos
    When: Entra desde un iPhone nuevo
    Then: Le llega el aviso
    """
    usuario = UserId(uuid4())
    ipad = _dispositivo(usuario, MAC, avisado_hace=timedelta(minutes=61))
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(ipad, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value))

    correo.send_new_login_notification.assert_awaited_once()


async def test_n9_unconfirmed_email_sends_nothing():
    """
    Given: Un usuario que aún no confirmó su correo
    When: Entra desde un dispositivo nuevo
    Then: No hay aviso: solo le llega el de confirmar
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value), verificado=False)

    correo.send_new_login_notification.assert_not_awaited()


async def test_n10_google_sign_up_sends_nothing():
    """
    Given: Alguien que crea la cuenta entrando con Google
    When: Se avisa
    Then: No hay correo: acaba de darse de alta
    """
    usuario = UserId(uuid4())
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(iphone)

    await _avisa(aviso, usuario, str(iphone.id.value), es_alta=True)

    correo.send_new_login_notification.assert_not_awaited()


async def test_n11_the_notice_is_recorded_on_the_device():
    """
    Given: Un dispositivo nuevo que avisa
    When: Se envía el correo
    Then: El dispositivo queda apuntado con la hora del aviso, guardado
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    uow, _, aviso = await _escena(mac, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value))

    guardado = await uow.user_devices.find_by_id(iphone.id)
    assert guardado.aviso_enviado_at == AHORA


async def test_n5b_an_email_that_was_not_sent_is_not_recorded():
    """
    Given: El proveedor de correo no lo envía (devuelve False, sin lanzar)
    When: Se avisa
    Then: El dispositivo no queda apuntado: el siguiente dispositivo nuevo podrá avisar
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, iphone)
    correo.send_new_login_notification.return_value = False

    await _avisa(aviso, usuario, str(iphone.id.value))

    assert iphone.aviso_enviado_at is None


async def test_n12_a_failure_logs_only_its_type_not_the_address(caplog):
    """
    Given: El proveedor de correo lanza un error que menciona la dirección
    When: Se avisa
    Then: El log dice solo el tipo de error, no la dirección (auditoría OWASP, A09)
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(0))
    _, correo, aviso = await _escena(mac, iphone)
    correo.send_new_login_notification.side_effect = RuntimeError("rechazado: ana@example.com")

    with caplog.at_level("DEBUG"):
        await _avisa(aviso, usuario, str(iphone.id.value))

    assert "RuntimeError" in caplog.text
    assert "ana@example.com" not in caplog.text


async def test_n13_the_email_says_when_the_sign_in_happened_not_when_the_device_was_created():
    """
    Given: Un iPhone dado de alta hace 30 días, que entra sin su cookie (lo reconoce la huella)
    When: Se avisa
    Then: El correo dice la hora del acceso (20:07 del 5 nov), no la del alta: con la del
          alta, un intruso con el mismo móvil parecería algo de hace un mes (revisión, 6 nov)
    """
    usuario = UserId(uuid4())
    mac = _dispositivo(usuario, MAC)
    iphone = _dispositivo(usuario, IPHONE, creado_hace=timedelta(days=30))
    _, correo, aviso = await _escena(mac, iphone)

    await _avisa(aviso, usuario, str(iphone.id.value))

    cuando = correo.send_new_login_notification.await_args.kwargs["cuando"]
    assert "5 nov 2026" in cuando and "20:07" in cuando
