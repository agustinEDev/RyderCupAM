"""
Revocar un dispositivo (BE #737, fase 4).

  #   caso                                              | esperado
  ----|------------------------------------------------|----------------------------------
  R1  revocar el dispositivo desde el que se mira         | el mensaje dice que es el actual,
                                                          |   por el `did`, no por la huella
  R2  revocar otro                                        | mensaje de otro
  R3  cada revocación                                     | queda en el historial de seguridad
"""

from unittest.mock import Mock

import pytest

from src.modules.user.application.dto.device_dto import (
    RegisterDeviceRequestDTO,
    RevokeDeviceRequestDTO,
)
from src.modules.user.application.use_cases.register_device_use_case import RegisterDeviceUseCase
from src.modules.user.application.use_cases.revoke_device_use_case import RevokeDeviceUseCase
from tests.unit.modules.user.application.use_cases._sesion_al_registrar import (
    uow_con_sesion_al_registrar,
)

pytestmark = pytest.mark.asyncio

USUARIO = "550e8400-e29b-41d4-a716-446655440000"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.1 Safari/605.1.15"


async def _dos():
    uow = uow_con_sesion_al_registrar()
    alta = RegisterDeviceUseCase(uow)
    iphone = (
        await alta.execute(
            RegisterDeviceRequestDTO(user_id=USUARIO, user_agent=IPHONE, ip_address="203.0.113.7")
        )
    ).device_id
    mac = (
        await alta.execute(
            RegisterDeviceRequestDTO(user_id=USUARIO, user_agent=MAC, ip_address="198.51.100.9")
        )
    ).device_id
    return uow, iphone, mac


async def test_r1_revoking_the_current_device_says_so_by_its_id():
    """
    Given: Un iPhone y un Mac, y la petición sale del Mac (su `did`) desde otra red
    When: Revoca el Mac
    Then: El mensaje dice que es el dispositivo actual, aunque la huella no coincida
    """
    uow, _, mac = await _dos()

    r = await RevokeDeviceUseCase(uow, Mock()).execute(
        RevokeDeviceRequestDTO(
            user_id=USUARIO,
            device_id=mac,
            current_device_id=mac,
            user_agent=MAC,
            ip_address="192.0.2.1",
        )
    )

    assert "actual" in r.message


async def test_r2_revoking_another_device_is_not_the_current_one():
    """
    Given: La petición sale del Mac
    When: Revoca el iPhone
    Then: El mensaje no habla del dispositivo actual
    """
    uow, iphone, mac = await _dos()

    r = await RevokeDeviceUseCase(uow, Mock()).execute(
        RevokeDeviceRequestDTO(user_id=USUARIO, device_id=iphone, current_device_id=mac)
    )

    assert "actual" not in r.message


async def test_r3_every_revocation_goes_to_the_security_log():
    """
    Given: Un dispositivo con su sesión
    When: Se revoca
    Then: Queda en el historial de seguridad, por su puerto: quién, qué dispositivo y
          cuántas sesiones cerró
    """
    registro = Mock()
    uow, iphone, mac = await _dos()

    await RevokeDeviceUseCase(uow, security_audit=registro).execute(
        RevokeDeviceRequestDTO(
            user_id=USUARIO,
            device_id=iphone,
            current_device_id=mac,
            ip_address="198.51.100.9",
            user_agent=MAC,
        )
    )

    registro.log_device_revoked.assert_called_once()
    kwargs = registro.log_device_revoked.call_args.kwargs
    assert kwargs["device_id"] == iphone
    assert kwargs["tokens_revoked_count"] == 1
    assert kwargs["user_id"] == USUARIO


async def test_r4_the_current_device_is_found_whatever_the_case_of_the_id():
    """
    Given: La petición sale del Mac y la ruta trae su id en mayúsculas
    When: Revoca el Mac
    Then: Sigue siendo el dispositivo actual
    """
    uow, _, mac = await _dos()

    r = await RevokeDeviceUseCase(uow, Mock()).execute(
        RevokeDeviceRequestDTO(user_id=USUARIO, device_id=mac.upper(), current_device_id=mac)
    )

    assert "actual" in r.message
