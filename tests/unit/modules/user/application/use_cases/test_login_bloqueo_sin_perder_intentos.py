"""
El contador de intentos fallidos no pierde sumas (BE #282).

El login leía al usuario, y en un fallo sumaba uno y guardaba el valor ABSOLUTO,
sin bloquear la fila: dos intentos a la vez leían N y escribían N+1. Cincuenta en
paralelo podían dejar un solo intento apuntado, y el bloqueo de los 10 no
saltaba nunca. Es la última defensa contra probar contraseñas.

Ahora, en el fallo, se relee al usuario CON la fila bloqueada y se suma sobre lo
releído. El bcrypt va antes y fuera de esa transacción: no la alarga 200 ms.

  #  caso                                         | qué se espera
  ---|------------------------------------------|----------------------------------
  1  contraseña mala                             | se relee con bloqueo y se suma
                                                   sobre lo RELEÍDO (5 → 6), no 0 → 1
  2  orden                                       | bcrypt antes del bloqueo
  3  lo releído ya va por 9                      | este intento bloquea la cuenta
  4  el usuario desaparece entre medias          | None, sin error
  5  contraseña buena                            | no se bloquea la fila
  —  N intentos a la vez de verdad               | test de integración, aparte
"""

from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases import login_user_use_case
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions import AccountLockedException
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService
from tests.unit.modules.user.application.use_cases.test_login_user_use_case import _rebuild_user

pytestmark = pytest.mark.asyncio

EMAIL = "bloqueo@example.com"
BUENA = "V@l1dP@ss123!"
MALA = "Mala-Pass-1!"


@pytest.fixture
async def escena():
    uow = InMemoryUnitOfWork()
    usuario = User.create(
        first_name="Ana", last_name="Bloqueo", email_str=EMAIL, plain_password=BUENA
    )
    async with uow:
        await uow.users.save(usuario)
    return uow, usuario, LoginUserUseCase(uow, JWTTokenService(), AsyncMock())


def _releido_con(uow, usuario, intentos, registro=None):
    """Lo que devuelve la relectura bloqueada: otra copia, que otro ya cambió."""
    copia = _rebuild_user(usuario, failed_login_attempts=intentos)
    pedidos = []

    async def bloqueada(user_id):
        pedidos.append(user_id)
        if registro is not None:
            registro.append("bloqueo")
        return copia

    uow.users.find_by_id_for_update = bloqueada
    return copia, pedidos


async def test_1_el_fallo_suma_sobre_lo_releido_con_bloqueo(escena):
    uow, usuario, login = escena
    copia, pedidos = _releido_con(uow, usuario, intentos=5)

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=MALA)) is None

    assert pedidos == [usuario.id]
    assert copia.failed_login_attempts == 6
    guardado = await uow.users.find_by_id(usuario.id)
    assert guardado.failed_login_attempts == 6


async def test_2_el_bcrypt_va_antes_del_bloqueo(escena, monkeypatch):
    uow, usuario, login = escena
    registro = []
    _releido_con(uow, usuario, intentos=0, registro=registro)
    original = login_user_use_case.run_bcrypt

    async def espia(funcion, *args, **kwargs):
        registro.append("bcrypt")
        return await original(funcion, *args, **kwargs)

    monkeypatch.setattr(login_user_use_case, "run_bcrypt", espia)

    await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))

    assert registro == ["bcrypt", "bloqueo"]


async def test_3_si_lo_releido_va_por_9_este_intento_bloquea(escena):
    uow, usuario, login = escena
    _releido_con(uow, usuario, intentos=9)

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))


async def test_4_si_el_usuario_desaparece_entre_medias_none_sin_error(escena):
    uow, _, login = escena

    async def borrado(_user_id):
        return None

    uow.users.find_by_id_for_update = borrado

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=MALA)) is None


async def test_5_con_la_contrasena_buena_no_se_bloquea_la_fila(escena):
    uow, usuario, login = escena
    _, pedidos = _releido_con(uow, usuario, intentos=0)

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA)) is not None

    assert pedidos == []
