"""
La app instalada y los dispositivos de antes de esta versión (BE #737).

  #    caso                                                  | esperado
  -----|----------------------------------------------------|-------------------------------
  RG2  la app instalada con la cookie de un dispositivo de    | queda como app instalada
       antes (marcado como navegador)                         |
  RG3  el navegador con la cookie de ese dispositivo          | vuelve a navegador: la última
                                                              |   conexión manda
"""

import pytest

from src.modules.user.application.dto.device_dto import RegisterDeviceRequestDTO
from src.modules.user.application.use_cases.register_device_use_case import RegisterDeviceUseCase
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

USUARIO = "550e8400-e29b-41d4-a716-446655440000"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"
IP = "203.0.113.7"


async def _de_antes():
    uow = InMemoryUnitOfWork()
    viejo = UserDevice.create(UserId(USUARIO), DeviceFingerprint.create(IPHONE, IP))
    await uow.user_devices.save(viejo)
    return uow, viejo


def _peticion(instalada, cookie=None):
    return RegisterDeviceRequestDTO(
        user_id=USUARIO,
        user_agent=IPHONE,
        ip_address=IP,
        installed_app=instalada,
        device_id_from_cookie=cookie,
    )


async def test_rg2_rg3_with_the_cookie_the_last_connection_says_app_or_browser():
    """
    Given: Un dispositivo de antes, marcado como navegador
    When: Entra con su cookie la app instalada, y luego el navegador
    Then: Queda como app instalada, y luego otra vez como navegador
    """
    uow, viejo = await _de_antes()
    alta = RegisterDeviceUseCase(uow)

    await alta.execute(_peticion(True, cookie=str(viejo.id.value)))
    assert (await uow.user_devices.find_by_id(viejo.id)).installed_app is True

    await alta.execute(_peticion(False, cookie=str(viejo.id.value)))
    assert (await uow.user_devices.find_by_id(viejo.id)).installed_app is False


async def test_rg4_it_says_whether_the_device_came_by_its_cookie():
    """
    Given: Un dispositivo conocido
    When: Entra con su cookie, y luego sin ella (la huella lo reconoce), y uno nuevo
    Then: Solo el primero viene «por su cookie»: los otros dos avisan (BE #737)
    """
    uow, viejo = await _de_antes()
    alta = RegisterDeviceUseCase(uow)

    con_cookie = await alta.execute(_peticion(False, cookie=str(viejo.id.value)))
    por_huella = await alta.execute(_peticion(False))
    nuevo = await alta.execute(
        RegisterDeviceRequestDTO(
            user_id=USUARIO, user_agent=IPHONE.replace("18_1", "17_0"), ip_address="198.51.100.9"
        )
    )

    assert con_cookie.recognized_by_cookie is True
    assert por_huella.recognized_by_cookie is False
    assert por_huella.device_id == str(viejo.id.value)
    assert nuevo.recognized_by_cookie is False
