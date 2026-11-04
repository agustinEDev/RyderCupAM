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
  5  contraseña buena, cuenta abierta           | se relee con bloqueo y se pone a 0
                                                   sobre lo RELEÍDO
  6  contraseña buena, pero otro la acaba de      | AccountLockedException: una
     bloquear (lo releído está bloqueado)          | ráfaga no cuela la buena (revisor)
  7  contraseña buena y el usuario desaparece     | None, sin error
  8  contraseña mala sobre una que otro acaba de   | se rechaza SIN contar: ni alarga
     bloquear                                      | el bloqueo ni repite el evento
  9  contraseña buena                              | el cero se guarda DENTRO de la
                                                   transacción bloqueada, antes de
                                                   seguir con el dispositivo
  —  N intentos a la vez de verdad               | test de integración, aparte
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

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


async def test_5_con_la_buena_se_pone_a_cero_sobre_lo_releido(escena):
    uow, usuario, login = escena
    copia, pedidos = _releido_con(uow, usuario, intentos=3)

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA)) is not None

    assert pedidos == [usuario.id]
    assert copia.failed_login_attempts == 0


async def test_6_con_la_buena_pero_recien_bloqueada_no_entra(escena):
    uow, usuario, login = escena
    _releido_con(uow, usuario, intentos=9)

    # Lo que dejó otro intento justo antes: el décimo fallo, que la bloquea
    async def bloqueada(_user_id):
        copia = _rebuild_user(usuario, failed_login_attempts=9)
        copia.record_failed_login()
        return copia

    uow.users.find_by_id_for_update = bloqueada

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA))


async def test_7_con_la_buena_y_el_usuario_desaparecido_none(escena):
    uow, _, login = escena

    async def borrado(_user_id):
        return None

    uow.users.find_by_id_for_update = borrado

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA)) is None


async def test_8_un_fallo_sobre_una_ya_bloqueada_no_cuenta(escena):
    uow, usuario, login = escena
    bloqueada = _rebuild_user(usuario, failed_login_attempts=9)
    bloqueada.record_failed_login()
    hasta = bloqueada.locked_until
    eventos = len(bloqueada.get_domain_events())

    async def releida(_user_id):
        return bloqueada

    uow.users.find_by_id_for_update = releida

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))

    assert bloqueada.failed_login_attempts == 10
    assert bloqueada.locked_until == hasta
    assert len(bloqueada.get_domain_events()) == eventos


async def test_9_el_cero_se_guarda_en_la_transaccion_bloqueada(escena):
    uow, usuario, login = escena
    registro = []
    _releido_con(uow, usuario, intentos=3, registro=registro)
    guardar = uow.users.save

    async def espia_save(user):
        registro.append(("save", user.failed_login_attempts))
        return await guardar(user)

    async def dispositivo(*_args, **_kwargs):
        registro.append("dispositivo")
        return SimpleNamespace(device_id=str(uuid4()), set_device_cookie=False)

    uow.users.save = espia_save
    login._register_device_use_case.execute = dispositivo

    await login.execute(
        LoginRequestDTO(email=EMAIL, password=BUENA, user_agent="Mozilla/5.0 pytest")
    )

    assert registro.index("bloqueo") < registro.index(("save", 0)) < registro.index("dispositivo")
