from unittest.mock import AsyncMock

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
  3  lo releído ya va por 49 (BE #732: el         | este intento bloquea el respaldo
     respaldo de la cuenta, 50 en una hora)        |
  4  el usuario desaparece entre medias          | None, sin error
  5  contraseña buena, cuenta abierta           | se relee con bloqueo, y el respaldo
                                                   NO vuelve a 0 (BE #732: suma todas
                                                   las redes; se acaba con su hora)
  6  contraseña buena, pero otro la acaba de      | AccountLockedException: una
     bloquear (lo releído está bloqueado)          | ráfaga no cuela la buena (revisor)
  7  contraseña buena y el usuario desaparece     | None, sin error
  8  contraseña mala sobre una que otro acaba de   | se rechaza SIN contar: ni alarga
     bloquear                                      | el bloqueo ni repite el evento
  9  contraseña buena                              | se relee con bloqueo ANTES de
                                                   seguir con el dispositivo, sin
                                                   guardar nada en esa transacción
  —  N intentos a la vez de verdad               | test de integración, aparte
"""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.config.freno_del_login import FrenoDelLoginEnMemoria
from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases import login_user_use_case
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import MAX_FAILED_ATTEMPTS, User
from src.modules.user.domain.exceptions import AccountLockedException
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService
from tests.unit.modules.user.application.use_cases._registro_falso import (
    registro_de_dispositivo_falso,
)
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
    return (
        uow,
        usuario,
        LoginUserUseCase(
            uow,
            JWTTokenService(),
            registro_de_dispositivo_falso(),
            AsyncMock(),
            FrenoDelLoginEnMemoria(),
            AsyncMock(),
        ),
    )


def _releido_con(uow, usuario, intentos, registro=None):
    """Lo que devuelve la relectura bloqueada: otra copia, que otro ya cambió."""
    # Con su hora abierta: el respaldo cuenta los fallos de la última hora (BE #732)
    copia = _rebuild_user(
        usuario, failed_login_attempts=intentos, failed_login_window_started_at=datetime.now()
    )
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
    Given: Lo releído va por 49 fallos en la última hora
    When: Llega otra contraseña mala
    Then: El respaldo de la cuenta queda bloqueado
    """
    uow, usuario, login = escena
    _releido_con(uow, usuario, intentos=MAX_FAILED_ATTEMPTS - 1)

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


async def test_login_success_rereads_and_keeps_the_backstop(escena):
    """
    Given: Lo releído tiene 3 fallos en la última hora
    When: Llega la contraseña buena
    Then: Se relee con bloqueo, y el respaldo sigue en 3: el dueño entrando no
          borra los fallos de un ataque repartido (BE #732)
    """
    uow, usuario, login = escena
    copia, pedidos = _releido_con(uow, usuario, intentos=3)

    assert await login.execute(LoginRequestDTO(email=EMAIL, password=BUENA)) is not None

    assert pedidos == [usuario.id]
    assert copia.failed_login_attempts == 3


async def test_login_success_on_account_locked_meanwhile_raises_locked(escena):
    """
    Given: La cuenta se bloquea entre la lectura y la relectura
    When: Llega la contraseña buena
    Then: AccountLockedException: no entra
    """
    uow, usuario, login = escena

    # Lo que dejó otro intento justo antes: el fallo 50, que bloquea el respaldo
    async def bloqueada(_user_id):
        """Ayudante del test: bloqueada."""
        copia = _rebuild_user(
            usuario,
            failed_login_attempts=MAX_FAILED_ATTEMPTS - 1,
            failed_login_window_started_at=datetime.now(),
        )
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
    bloqueada = _rebuild_user(
        usuario,
        failed_login_attempts=MAX_FAILED_ATTEMPTS - 1,
        failed_login_window_started_at=datetime.now(),
    )
    bloqueada.record_failed_login()
    hasta = bloqueada.locked_until
    fallos = bloqueada.failed_login_attempts
    eventos = len(bloqueada.get_domain_events())

    async def releida(_user_id):
        """Ayudante del test: releida."""
        return bloqueada

    uow.users.find_by_id_for_update = releida

    with pytest.raises(AccountLockedException):
        await login.execute(LoginRequestDTO(email=EMAIL, password=MALA))

    assert bloqueada.failed_login_attempts == fallos
    assert bloqueada.locked_until == hasta
    assert len(bloqueada.get_domain_events()) == eventos


async def test_login_success_rereads_before_the_device_and_saves_nothing_there(escena):
    """
    Given: La contraseña buena
    When: Se procesa el intento
    Then: Relee con bloqueo antes del dispositivo, y no guarda el usuario hasta
          después (ya no hay cero que guardar: BE #732)
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
        return SimpleNamespace(
            device_id=str(uuid4()),
            is_new_device=False,
            recognized_by_cookie=True,
        )

    uow.users.save = espia_save
    login._register_device_use_case.execute = dispositivo

    await login.execute(
        LoginRequestDTO(email=EMAIL, password=BUENA, user_agent="Mozilla/5.0 pytest")
    )

    guardados = [i for i, r in enumerate(registro) if isinstance(r, tuple)]
    assert registro.index("bloqueo") < registro.index("dispositivo") < min(guardados)
