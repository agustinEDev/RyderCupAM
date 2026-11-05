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
    """Ayudante del test: escena."""
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
        """Ayudante del test: bloqueada."""
        pedidos.append(user_id)
        if registro is not None:
            registro.append("bloqueo")
        return copia

    uow.users.find_by_id_for_update = bloqueada
    return copia, pedidos


async def test_login_failure_increments_reread_locked_counter(escena):
    """
    Given: Otro intento subió el contador tras la primera lectura
    When: Llega una contraseña mala
    Then: Suma sobre lo releído con bloqueo
    """
    uow, usuario, login = escena
    copia, pedidos = _releido_con(uow, usuario, intentos=5)

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=MALA)) is None

    assert pedidos == [usuario.id]
    assert copia.failed_login_attempts == 6
    guardado = await uow.users.find_by_id(usuario.id)
    assert guardado.failed_login_attempts == 6


async def test_login_failure_runs_bcrypt_before_locking_row(escena, monkeypatch):
    """
    Given: Una contraseña mala
    When: Se procesa el intento
    Then: bcrypt corre antes de bloquear la fila
    """
    uow, usuario, login = escena
    registro = []
    _releido_con(uow, usuario, intentos=0, registro=registro)
    original = login_user_use_case.run_bcrypt

    async def espia(funcion, *args, **kwargs):
        """Ayudante del test: espia."""
        registro.append("bcrypt")
        return await original(funcion, *args, **kwargs)

    monkeypatch.setattr(login_user_use_case, "run_bcrypt", espia)

    await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))

    assert registro == ["bcrypt", "bloqueo"]


async def test_login_failure_with_reread_counter_at_nine_locks_account(escena):
    """
    Given: Lo releído va por 9 fallos
    When: Llega otra contraseña mala
    Then: La cuenta queda bloqueada
    """
    uow, usuario, login = escena
    _releido_con(uow, usuario, intentos=9)

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))


async def test_login_failure_user_deleted_meanwhile_returns_none(escena):
    """
    Given: El usuario se borra antes de la relectura
    When: Llega una contraseña mala
    Then: Devuelve None sin error
    """
    uow, _, login = escena

    async def borrado(_user_id):
        """Ayudante del test: borrado."""
        return

    uow.users.find_by_id_for_update = borrado

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=MALA)) is None


async def test_login_success_resets_reread_counter(escena):
    """
    Given: Lo releído tiene fallos apuntados
    When: Llega la contraseña buena
    Then: El contador vuelve a cero sobre lo releído
    """
    uow, usuario, login = escena
    copia, pedidos = _releido_con(uow, usuario, intentos=3)

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA)) is not None

    assert pedidos == [usuario.id]
    assert copia.failed_login_attempts == 0


async def test_login_success_on_account_locked_meanwhile_raises_locked(escena):
    """
    Given: La cuenta se bloquea entre la lectura y la relectura
    When: Llega la contraseña buena
    Then: AccountLockedException: no entra
    """
    uow, usuario, login = escena
    _releido_con(uow, usuario, intentos=9)

    # Lo que dejó otro intento justo antes: el décimo fallo, que la bloquea
    async def bloqueada(_user_id):
        """Ayudante del test: bloqueada."""
        copia = _rebuild_user(usuario, failed_login_attempts=9)
        copia.record_failed_login()
        return copia

    uow.users.find_by_id_for_update = bloqueada

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA))


async def test_login_success_user_deleted_meanwhile_returns_none(escena):
    """
    Given: El usuario se borra antes de la relectura
    When: Llega la contraseña buena
    Then: Devuelve None
    """
    uow, _, login = escena

    async def borrado(_user_id):
        """Ayudante del test: borrado."""
        return

    uow.users.find_by_id_for_update = borrado

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA)) is None


async def test_login_failure_on_locked_account_does_not_count(escena):
    """
    Given: Una cuenta ya bloqueada al releer
    When: Llega una contraseña mala
    Then: El contador no sube
    """
    uow, usuario, login = escena
    bloqueada = _rebuild_user(usuario, failed_login_attempts=9)
    bloqueada.record_failed_login()
    hasta = bloqueada.locked_until
    eventos = len(bloqueada.get_domain_events())

    async def releida(_user_id):
        """Ayudante del test: releida."""
        return bloqueada

    uow.users.find_by_id_for_update = releida

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))

    assert bloqueada.failed_login_attempts == 10
    assert bloqueada.locked_until == hasta
    assert len(bloqueada.get_domain_events()) == eventos


async def test_login_success_saves_reset_inside_locked_transaction(escena):
    """
    Given: La contraseña buena
    When: Se procesa el intento
    Then: El cero se guarda en la misma transacción que bloqueó la fila
    """
    uow, usuario, login = escena
    registro = []
    _releido_con(uow, usuario, intentos=3, registro=registro)
    guardar = uow.users.save

    async def espia_save(user):
        """Ayudante del test: espia save."""
        registro.append(("save", user.failed_login_attempts))
        return await guardar(user)

    async def dispositivo(*_args, **_kwargs):
        """Ayudante del test: dispositivo."""
        registro.append("dispositivo")
        return SimpleNamespace(device_id=str(uuid4()), set_device_cookie=False, is_new_device=False)

    uow.users.save = espia_save
    login._register_device_use_case.execute = dispositivo

    await login.execute(
        LoginRequestDTO(email=EMAIL, password=BUENA, user_agent="Mozilla/5.0 pytest")
    )

    assert registro.index("bloqueo") < registro.index(("save", 0)) < registro.index("dispositivo")
