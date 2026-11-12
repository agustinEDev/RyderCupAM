"""
Un email que no existe cuesta lo mismo que una contraseña mala (BE #281).

El login devolvía enseguida cuando el email no existía, sin pasar por bcrypt, y
todo lo demás paga ~200 ms de hash. Medido contra producción: un fallo con una
cuenta que existe tardaba ~589 ms y `/health` ~86 ms. Con el cronómetro se sabía
quién está registrado (OWASP A07): saber que un email juega en esta liga ya es
un dato personal, y le da al atacante la lista de cuentas buenas antes de probar
una sola contraseña.

  #  caso                                         | qué se espera
  ---|------------------------------------------|----------------------------------
  1  email inexistente                           | bcrypt UNA vez, y None
  2  email existente, contraseña mala            | bcrypt UNA vez, y None (igual)
  3  el hash de relleno                          | con el MISMO coste que los reales
  4  dos logins con emails inexistentes          | el relleno se calcula una sola vez
  5  ninguna contraseña entra por el relleno     | siempre False, también la vacía
  6  email inexistente                           | por `run_bcrypt` (#272), fuera
                                                   del bucle de eventos
  7  cuenta solo de Google (sin contraseña)      | bcrypt UNA vez también: si no,
                                                   se delata por tiempo (code-review)
"""

from unittest.mock import AsyncMock

import bcrypt
import pytest

from src.config.freno_del_login import FrenoDelLoginEnMemoria
from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases import login_user_use_case
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.infrastructure.security import bcrypt_password_hasher as adaptador
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.infrastructure.security.jwt_handler import JWTTokenService
from tests.unit.modules.user.application.use_cases.test_login_user_use_case import _rebuild_user

pytestmark = pytest.mark.asyncio


@pytest.fixture
def cuenta_checkpw(monkeypatch):
    """Cuenta las verificaciones de bcrypt que se hacen de verdad."""
    llamadas = []
    original = bcrypt.checkpw

    def espia(*args, **kwargs):
        """Ayudante del test: espia."""
        llamadas.append(args)
        return original(*args, **kwargs)

    # El bcrypt de verdad lo llama el adaptador del puerto PasswordHasher
    monkeypatch.setattr(adaptador.bcrypt, "checkpw", espia)
    return llamadas


@pytest.fixture
def caso_de_uso():
    """Ayudante del test: caso de uso."""
    uow = InMemoryUnitOfWork()
    dispositivos = AsyncMock()
    return uow, LoginUserUseCase(
        uow,
        JWTTokenService(),
        dispositivos,
        AsyncMock(),
        FrenoDelLoginEnMemoria(),
        AsyncMock(),
        security_audit=SecurityAuditLogger(),
    )


async def _con_usuario(uow) -> User:
    """Ayudante del test: con usuario."""
    usuario = User.create(
        first_name="Ana",
        last_name="Existe",
        email_str="existe@example.com",
        plain_password="V@l1dP@ss123!",
    )
    async with uow:
        await uow.users.save(usuario)
    return usuario


async def test_login_unknown_email_runs_bcrypt_once(caso_de_uso, cuenta_checkpw):
    """
    Given: Un email que no existe
    When: Se intenta entrar
    Then: bcrypt corre una vez, como con un usuario real
    """
    _, login = caso_de_uso

    respuesta = await login.execute(
        LoginRequestDTO(email="nadie@example.com", password="Lo-Que-Sea-1")
    )

    assert respuesta is None
    assert len(cuenta_checkpw) == 1


async def test_login_wrong_password_runs_bcrypt_once(caso_de_uso, cuenta_checkpw):
    """
    Given: Un usuario existente
    When: Se entra con la contraseña mala
    Then: bcrypt corre una vez
    """
    uow, login = caso_de_uso
    await _con_usuario(uow)

    respuesta = await login.execute(
        LoginRequestDTO(email="existe@example.com", password="Mala-Pass-1!")
    )

    assert respuesta is None
    assert len(cuenta_checkpw) == 1


def test_dummy_hash_has_same_cost_as_real_hashes():
    """
    Given: El hash de relleno
    When: Se mira su coste
    Then: Es el mismo que el de los hashes reales
    """
    real = Password.from_plain_text("V@l1dP@ss123!").hashed_value
    relleno = Password._relleno()

    # `$2b$<coste>$...`: el coste es el tercer campo
    assert relleno.split("$")[2] == real.split("$")[2]
    assert relleno.startswith("$2")


def test_dummy_hash_in_production_has_cost_12():
    """
    Given: El hasher de producción (bcrypt con las rondas por defecto)
    When: Se calcula el relleno
    Then: Su coste es 12
    """
    from src.config.contrasenas import rondas_de_bcrypt
    from src.modules.user.domain.ports import password_hasher
    from src.modules.user.infrastructure.security.bcrypt_password_hasher import (
        BcryptPasswordHasher,
    )

    anterior = password_hasher._instalado
    password_hasher.instala_el_hasher(BcryptPasswordHasher(rounds=rondas_de_bcrypt({})))
    Password._relleno.cache_clear()
    try:
        assert Password._relleno().split("$")[2] == "12"
    finally:
        password_hasher._instalado = anterior
        Password._relleno.cache_clear()


async def test_dummy_hash_is_computed_once(caso_de_uso, monkeypatch):
    """
    Given: Varios logins con email inexistente
    When: Se procesan
    Then: El relleno se calcula una sola vez
    """
    _, login = caso_de_uso
    Password._relleno.cache_clear()
    hechos = []
    original = Password._hash_password

    def espia(texto):
        """Ayudante del test: espia."""
        hechos.append(1)
        return original(texto)

    monkeypatch.setattr(Password, "_hash_password", staticmethod(espia))

    await login.execute(LoginRequestDTO(email="uno@example.com", password="Lo-Que-Sea-1"))
    await login.execute(LoginRequestDTO(email="dos@example.com", password="Lo-Que-Sea-2"))

    assert len(hechos) == 1


@pytest.mark.parametrize("intento", ["", "Lo-Que-Sea-1", "x" * 200, "ñandú-🙂"])
def test_dummy_hash_never_verifies_any_password(intento):
    """
    Given: Una contraseña cualquiera
    When: Se verifica contra el relleno
    Then: Siempre es False
    """
    assert Password.verifica_contra_el_relleno(intento) is False


async def test_login_unknown_email_verifies_dummy_via_run_bcrypt(caso_de_uso, monkeypatch):
    """
    Given: Un email que no existe
    When: Se intenta entrar
    Then: La verificación del relleno va por run_bcrypt, fuera del bucle de eventos
    """
    _, login = caso_de_uso
    pasadas = []
    original = login_user_use_case.run_bcrypt

    async def espia(funcion, *args, **kwargs):
        """Ayudante del test: espia."""
        pasadas.append(funcion)
        return await original(funcion, *args, **kwargs)

    monkeypatch.setattr(login_user_use_case, "run_bcrypt", espia)

    await login.execute(LoginRequestDTO(email="nadie@example.com", password="Lo-Que-Sea-1"))

    assert pasadas == [Password.verifica_contra_el_relleno]


async def test_login_google_only_account_runs_bcrypt_once(caso_de_uso, cuenta_checkpw):
    """
    Given: Una cuenta solo de Google, sin contraseña
    When: Se intenta entrar con contraseña
    Then: bcrypt corre una vez igualmente
    """
    uow, login = caso_de_uso
    usuario = User.create(
        first_name="Ana",
        last_name="Google",
        email_str="google@example.com",
        plain_password="V@l1dP@ss123!",
    )
    sin_contrasena = _rebuild_user(usuario, password=None)
    async with uow:
        await uow.users.save(sin_contrasena)

    respuesta = await login.execute(
        LoginRequestDTO(email="google@example.com", password="Lo-Que-Sea-1")
    )

    assert respuesta is None
    assert len(cuenta_checkpw) == 1
