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
"""

from unittest.mock import AsyncMock

import bcrypt
import pytest

from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases import login_user_use_case
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects import password as modulo_password
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def cuenta_checkpw(monkeypatch):
    """Cuenta las verificaciones de bcrypt que se hacen de verdad."""
    llamadas = []
    original = bcrypt.checkpw

    def espia(*args, **kwargs):
        llamadas.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(modulo_password.bcrypt, "checkpw", espia)
    return llamadas


@pytest.fixture
def caso_de_uso():
    uow = InMemoryUnitOfWork()
    dispositivos = AsyncMock()
    return uow, LoginUserUseCase(uow, JWTTokenService(), dispositivos)


async def _con_usuario(uow) -> User:
    usuario = User.create(
        first_name="Ana",
        last_name="Existe",
        email_str="existe@example.com",
        plain_password="V@l1dP@ss123!",
    )
    async with uow:
        await uow.users.save(usuario)
    return usuario


async def test_1_un_email_inexistente_pasa_por_bcrypt_una_vez(caso_de_uso, cuenta_checkpw):
    _, login = caso_de_uso

    respuesta = await login.execute(
        LoginRequestDTO(email="nadie@example.com", password="Lo-Que-Sea-1")
    )

    assert respuesta is None
    assert len(cuenta_checkpw) == 1


async def test_2_una_contrasena_mala_tambien_una_vez(caso_de_uso, cuenta_checkpw):
    uow, login = caso_de_uso
    await _con_usuario(uow)

    respuesta = await login.execute(
        LoginRequestDTO(email="existe@example.com", password="Mala-Pass-1!")
    )

    assert respuesta is None
    assert len(cuenta_checkpw) == 1


def test_3_el_relleno_tiene_el_mismo_coste_que_los_hashes_reales():
    real = Password.from_plain_text("V@l1dP@ss123!").hashed_value
    relleno = Password.hash_de_relleno()

    # `$2b$<coste>$...`: el coste es el tercer campo
    assert relleno.split("$")[2] == real.split("$")[2]
    assert relleno.startswith("$2")


def test_3b_en_produccion_el_coste_es_12(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    Password._relleno.cache_clear()
    try:
        assert Password.hash_de_relleno().split("$")[2] == "12"
    finally:
        Password._relleno.cache_clear()


async def test_4_el_relleno_se_calcula_una_sola_vez(caso_de_uso, monkeypatch):
    _, login = caso_de_uso
    Password._relleno.cache_clear()
    hechos = []
    original = Password._hash_password

    def espia(texto):
        hechos.append(1)
        return original(texto)

    monkeypatch.setattr(Password, "_hash_password", staticmethod(espia))

    await login.execute(LoginRequestDTO(email="uno@example.com", password="Lo-Que-Sea-1"))
    await login.execute(LoginRequestDTO(email="dos@example.com", password="Lo-Que-Sea-2"))

    assert len(hechos) == 1


@pytest.mark.parametrize("intento", ["", "Lo-Que-Sea-1", "x" * 200, "ñandú-🙂"])
def test_5_ninguna_contrasena_entra_por_el_relleno(intento):
    assert Password.verifica_contra_el_relleno(intento) is False


async def test_6_el_relleno_va_por_run_bcrypt(caso_de_uso, monkeypatch):
    _, login = caso_de_uso
    pasadas = []
    original = login_user_use_case.run_bcrypt

    async def espia(funcion, *args, **kwargs):
        pasadas.append(funcion)
        return await original(funcion, *args, **kwargs)

    monkeypatch.setattr(login_user_use_case, "run_bcrypt", espia)

    await login.execute(LoginRequestDTO(email="nadie@example.com", password="Lo-Que-Sea-1"))

    assert pasadas == [Password.verifica_contra_el_relleno]
