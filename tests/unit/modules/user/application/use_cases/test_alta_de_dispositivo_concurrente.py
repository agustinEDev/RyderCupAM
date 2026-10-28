"""
Dos inicios de sesión a la vez del mismo dispositivo (BE #692, tabla del 28 oct 2026).

Los dos leen «no hay dispositivo» y los dos lo dan de alta: el índice único
parcial (usuario, huella, activo) rechazaba al segundo con un 500. Ahora el alta
es «dar de alta si no lo está»: el segundo reutiliza el del primero (S1), en el
login, la renovación y Google, que pasan todos por aquí (S2).
"""

import pytest

from src.modules.user.application.dto.device_dto import RegisterDeviceRequestDTO
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

AGENTE = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"
IP = "192.168.1.100"


async def test_s1_si_otro_lo_dio_de_alta_entre_medias_se_reutiliza(monkeypatch):
    uow = InMemoryUnitOfWork()
    user_id = UserId.generate()
    del_otro = UserDevice.create(
        user_id=user_id, fingerprint=DeviceFingerprint.create(user_agent=AGENTE, ip_address=IP)
    )

    # La lectura de este login llega antes que el alta del otro: no lo ve. Lo
    # que se mire después, ya con el del otro guardado, sí
    leer = uow.user_devices.find_by_user_and_fingerprint
    lecturas = []

    async def la_primera_no_lo_ve(*args, **kwargs):
        lecturas.append(args or kwargs)
        if len(lecturas) == 1:
            await uow.user_devices.save(del_otro)
            return None
        return await leer(*args, **kwargs)

    monkeypatch.setattr(uow.user_devices, "find_by_user_and_fingerprint", la_primera_no_lo_ve)

    respuesta = await RegisterDeviceUseCase(uow).execute(
        RegisterDeviceRequestDTO(user_id=str(user_id.value), user_agent=AGENTE, ip_address=IP)
    )

    assert respuesta.device_id == str(del_otro.id.value)
    assert respuesta.is_new_device is False
    assert respuesta.set_device_cookie is True
    async with uow:
        activos = await uow.user_devices.find_active_by_user(user_id)
    assert [d.id for d in activos] == [del_otro.id]


async def test_sin_carrera_se_da_de_alta_como_siempre():
    uow = InMemoryUnitOfWork()
    user_id = UserId.generate()

    respuesta = await RegisterDeviceUseCase(uow).execute(
        RegisterDeviceRequestDTO(user_id=str(user_id.value), user_agent=AGENTE, ip_address=IP)
    )

    assert respuesta.is_new_device is True
