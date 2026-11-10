"""
El correo «Hemos cerrado tu sesión en un dispositivo por seguridad» (F-02, caso A4).

  #   caso                                      | ¿correo?
  ----|-----------------------------------------|---------------------------------------
  C1  robo detectado, correo confirmado         | sí: dispositivo, hora de España y país
  C2  su correo aún no está confirmado          | no: como los demás avisos de seguridad
  C3  el dispositivo ya no existe               | no (y no lanza)
  C4  falla el envío o el proveedor lanza       | no lanza: el refresco no depende de él
  C5  sin país                                  | el correo no lo menciona
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.device_dto import AvisoDeSesionCerradaRequestDTO
from src.modules.user.application.services.aviso_de_sesion_cerrada_por_seguridad import (
    AvisoDeSesionCerradaPorSeguridad,
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
# 10 nov 2026, 11:30 UTC = 12:30 en la península
AHORA = datetime(2026, 11, 10, 11, 30)


class _Paises:
    async def find_by_code(self, code: CountryCode):
        if code.value == "ES":
            return Country(code=CountryCode("ES"), name_en="Spain", name_es="España")
        return None


async def _escena(pais: str | None = "ES"):
    usuario = UserId(uuid4())
    iphone = UserDevice.create(
        usuario, DeviceFingerprint.create(IPHONE, "203.0.113.7"), country_code=pais
    )
    uow = InMemoryUnitOfWork()
    await uow.user_devices.save(iphone)
    correo = AsyncMock()
    correo.send_session_closed_for_security_notice.return_value = True
    aviso = AvisoDeSesionCerradaPorSeguridad(uow, correo, _Paises(), reloj=lambda: AHORA)
    return usuario, iphone, correo, aviso


def _peticion(usuario, device_id, verificado=True) -> AvisoDeSesionCerradaRequestDTO:
    return AvisoDeSesionCerradaRequestDTO(
        user_id=str(usuario.value),
        email="ana@example.com",
        nombre="Ana",
        device_id=device_id,
        verificado=verificado,
    )


async def test_c1_sends_the_notice_with_device_time_and_country():
    """
    Given: Un robo detectado en el iPhone de Ana, en España, con su correo confirmado
    When: Se avisa
    Then: Le llega el correo con «iPhone · Safari», la hora de España (12:30) y «España»
    """
    usuario, iphone, correo, aviso = await _escena()

    await aviso.avisa(_peticion(usuario, str(iphone.id.value)))

    correo.send_session_closed_for_security_notice.assert_awaited_once()
    kwargs = correo.send_session_closed_for_security_notice.await_args.kwargs
    assert kwargs["to_email"] == "ana@example.com"
    assert kwargs["user_name"] == "Ana"
    assert kwargs["dispositivo"] == "iPhone · Safari"
    assert "12:30" in kwargs["cuando"] and "10 nov 2026" in kwargs["cuando"]
    assert kwargs["pais"] == "España"


async def test_c2_an_unconfirmed_email_gets_nothing():
    """
    Given: Su correo aún no está confirmado
    Then: No se manda nada (no mandamos avisos de seguridad a una dirección quizá ajena)
    """
    usuario, iphone, correo, aviso = await _escena()

    await aviso.avisa(_peticion(usuario, str(iphone.id.value), verificado=False))

    correo.send_session_closed_for_security_notice.assert_not_awaited()


async def test_c3_a_missing_device_sends_nothing():
    """
    Given: Un dispositivo que ya no está (o es de otro usuario)
    Then: Nada, y no lanza
    """
    _usuario, iphone, correo, aviso = await _escena()

    await aviso.avisa(_peticion(UserId(uuid4()), str(iphone.id.value)))

    correo.send_session_closed_for_security_notice.assert_not_awaited()


@pytest.mark.parametrize("fallo", ["devuelve_false", "lanza"])
async def test_c4_a_failing_send_never_raises(fallo):
    """
    Given: El proveedor no lo manda (False) o lanza
    When: Se avisa
    Then: No lanza
    """
    usuario, iphone, correo, aviso = await _escena()
    if fallo == "lanza":
        correo.send_session_closed_for_security_notice.side_effect = RuntimeError("caído")
    else:
        correo.send_session_closed_for_security_notice.return_value = False

    await aviso.avisa(_peticion(usuario, str(iphone.id.value)))

    correo.send_session_closed_for_security_notice.assert_awaited_once()


async def test_c5_without_a_country_it_is_not_mentioned():
    """
    Given: Un dispositivo sin país
    Then: El correo sale con país None
    """
    usuario, iphone, correo, aviso = await _escena(pais=None)

    await aviso.avisa(_peticion(usuario, str(iphone.id.value)))

    assert correo.send_session_closed_for_security_notice.await_args.kwargs["pais"] is None
