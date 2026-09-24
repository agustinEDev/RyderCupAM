"""Cerrar sesión cierra ESTE dispositivo, no todos (BE #376).

Hasta el 24 sep el logout revocaba todos los tokens de refresco de la persona.
Junto con el cierre por inactividad del frontend, una ventana olvidada en casa
echaba al jugador del móvil en el campo, donde sin cobertura no puede volver a
entrar. «Salir de todos» es revocar dispositivos desde su gestión.

    #   caso                                             | qué pasa
    ----|------------------------------------------------|------------------------------
    L1  dos dispositivos, sale en A                      | A revocado, B sigue
    L2  A guarda tokens de logins anteriores             | todos los de A, B sigue
    L3  sin token de refresco en la petición             | no se revoca nada
    L4  el token que llega es de otra persona            | no se toca
"""

import pytest

from src.modules.user.application.dto.user_dto import LogoutRequestDTO
from src.modules.user.application.use_cases.logout_user_use_case import LogoutUserUseCase
from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


async def _persona(uow, email: str) -> User:
    user = User.create(
        first_name="Ana", last_name="Golf", email_str=email, plain_password="V@l1dP@ss123!"
    )
    async with uow:
        await uow.users.save(user)
    return user


async def _sesion(uow, user: User, jwt: str, device: UserDeviceId | None) -> None:
    async with uow:
        await uow.refresh_tokens.save(RefreshToken.create(user.id, jwt, device_id=device))


async def _revocado(uow, jwt: str) -> bool:
    async with uow:
        return (await uow.refresh_tokens.find_by_token_hash(jwt)).revoked


def _salir(refresh_token: str | None) -> LogoutRequestDTO:
    return LogoutRequestDTO(refresh_token=refresh_token)


async def test_l1_salir_en_un_dispositivo_no_cierra_los_demas():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow, "ana@example.com")
    await _sesion(uow, ana, "jwt-ordenador", UserDeviceId.generate())
    await _sesion(uow, ana, "jwt-movil", UserDeviceId.generate())

    await LogoutUserUseCase(uow).execute(_salir("jwt-ordenador"), str(ana.id.value))

    assert await _revocado(uow, "jwt-ordenador") is True
    assert await _revocado(uow, "jwt-movil") is False


async def test_l2_se_cierran_todas_las_de_ese_dispositivo():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow, "ana@example.com")
    ordenador = UserDeviceId.generate()
    await _sesion(uow, ana, "jwt-ordenador-ayer", ordenador)
    await _sesion(uow, ana, "jwt-ordenador-hoy", ordenador)
    await _sesion(uow, ana, "jwt-movil", UserDeviceId.generate())

    await LogoutUserUseCase(uow).execute(_salir("jwt-ordenador-hoy"), str(ana.id.value))

    assert await _revocado(uow, "jwt-ordenador-ayer") is True
    assert await _revocado(uow, "jwt-ordenador-hoy") is True
    assert await _revocado(uow, "jwt-movil") is False


async def test_l3_sin_token_de_refresco_no_se_revoca_nada():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow, "ana@example.com")
    await _sesion(uow, ana, "jwt-movil", UserDeviceId.generate())

    respuesta = await LogoutUserUseCase(uow).execute(_salir(None), str(ana.id.value))

    assert respuesta is not None
    assert await _revocado(uow, "jwt-movil") is False


async def test_l4_no_se_revoca_el_token_de_otra_persona():
    uow = InMemoryUnitOfWork()
    ana = await _persona(uow, "ana@example.com")
    luis = await _persona(uow, "luis@example.com")
    # Sin dispositivo es el caso peligroso: ahí se revocaría el token tal cual llega
    await _sesion(uow, luis, "jwt-de-luis", None)
    await _sesion(uow, luis, "jwt-de-luis-movil", UserDeviceId.generate())

    await LogoutUserUseCase(uow).execute(_salir("jwt-de-luis"), str(ana.id.value))
    await LogoutUserUseCase(uow).execute(_salir("jwt-de-luis-movil"), str(ana.id.value))

    assert await _revocado(uow, "jwt-de-luis") is False
    assert await _revocado(uow, "jwt-de-luis-movil") is False
