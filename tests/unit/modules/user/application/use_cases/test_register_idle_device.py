"""Volver a un dispositivo inactivo no resucita sus tokens viejos (BE #376).

La caducidad por inactividad (24 h) revoca un token cuando se intenta refrescar
con él. Pero si el dispositivo lleva días parado y alguien vuelve a entrar desde
él, el login le pone «último uso: ahora», y los tokens viejos de ese
dispositivo —que nadie había intentado usar— volverían a valer. Uno robado
también (CWE-613, CodeRabbit en la #378). Antes de reanudar un dispositivo
inactivo, sus tokens anteriores se revocan.

    #   caso                                               | qué pasa
    ----|--------------------------------------------------|------------------------
    C1  vuelve a un dispositivo inactivo (por cookie)      | sus tokens viejos, revocados
    C2  lo mismo, reconocido por huella                    | revocados
    C3  dispositivo activo                                 | sus tokens siguen valiendo
"""

from datetime import datetime, timedelta

import pytest

from src.modules.user.application.dto.device_dto import RegisterDeviceRequestDTO
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) Mobile/15E148 Safari/604.1"
IP = "10.0.0.7"


async def _dispositivo_con_token(uow, user_id: UserId, usado_hace: timedelta) -> UserDevice:
    huella = DeviceFingerprint.create(user_agent=UA, ip_address=IP)
    ahora = datetime.now()
    dispositivo = UserDevice(
        id=UserDeviceId.generate(),
        user_id=user_id,
        device_name=huella.device_name,
        user_agent=UA,
        ip_address=IP,
        fingerprint_hash=huella.fingerprint_hash,
        is_active=True,
        last_used_at=ahora - usado_hace,
        created_at=ahora - timedelta(days=5),
    )
    async with uow:
        await uow.user_devices.save(dispositivo)
        await uow.refresh_tokens.save(RefreshToken.create(user_id, "jwt-viejo", dispositivo.id))
    return dispositivo


async def _revocado(uow) -> bool:
    async with uow:
        return (await uow.refresh_tokens.find_by_token_hash("jwt-viejo")).revoked


@pytest.mark.parametrize("por_cookie", [pytest.param(True, id="C1"), pytest.param(False, id="C2")])
async def test_volver_a_un_dispositivo_inactivo_revoca_sus_tokens_viejos(por_cookie):
    uow = InMemoryUnitOfWork()
    user_id = UserId.generate()
    dispositivo = await _dispositivo_con_token(uow, user_id, timedelta(days=3))

    await RegisterDeviceUseCase(uow).execute(
        RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            user_agent=UA,
            ip_address=IP,
            device_id_from_cookie=str(dispositivo.id.value) if por_cookie else None,
        )
    )

    assert await _revocado(uow) is True


async def test_c3_un_dispositivo_activo_conserva_sus_tokens():
    uow = InMemoryUnitOfWork()
    user_id = UserId.generate()
    dispositivo = await _dispositivo_con_token(uow, user_id, timedelta(hours=2))

    await RegisterDeviceUseCase(uow).execute(
        RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            user_agent=UA,
            ip_address=IP,
            device_id_from_cookie=str(dispositivo.id.value),
        )
    )

    assert await _revocado(uow) is False
