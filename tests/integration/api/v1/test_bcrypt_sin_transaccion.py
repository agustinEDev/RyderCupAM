"""
Ningún bcrypt con una transacción abierta (BE #283, B2-7, 7 nov 2026).

bcrypt tarda a propósito (~250 ms). Con una transacción abierta retiene una conexión del
pool, y con la fila del usuario bloqueada hace esperar a todo lo que la toque. Estos tests
recorren de verdad cada camino y, en el momento de cada bcrypt, miran que ninguna sesión
viva de SQLAlchemy esté dentro de una transacción.

  B2-1 alta (y con el correo ocupado: ningún bcrypt)
  B2-2 login: bueno, malo y con un correo que no existe (el bcrypt de relleno)
  B2-3 cambio de contraseña (la actual, el historial y la nueva)
  B2-4 restablecer la contraseña
  B2-5 la cuenta de sistema (contra la BD real, fuera de una petición)
  Y, tras los revisores, el login con la cookie de dispositivo y el cambio solo de correo
"""

import importlib
import weakref

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import create_authenticated_user, token_de_reset_enviado

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"
NUEVA = "N3w$ecureP@ss99"

MODULOS = [
    "src.modules.user.application.use_cases.register_user_use_case",
    "src.modules.user.application.use_cases.login_user_use_case",
    "src.modules.user.application.use_cases.update_security_use_case",
    "src.modules.user.application.use_cases.reset_password_use_case",
    "src.modules.user.application.use_cases.ensure_system_user_use_case",
]


class _Vigia:
    """Apunta cada sesión que se abre y, en cada bcrypt, si alguna está en transacción."""

    def __init__(self):
        self.sesiones: weakref.WeakSet[AsyncSession] = weakref.WeakSet()
        self.bcrypts = 0
        self.con_transaccion: list[str] = []


@pytest.fixture
def vigia(monkeypatch):
    vigia = _Vigia()
    original_init = AsyncSession.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        vigia.sesiones.add(self)

    monkeypatch.setattr(AsyncSession, "__init__", init)

    for nombre in MODULOS:
        modulo = importlib.import_module(nombre)
        real = modulo.run_bcrypt

        async def vigilado(func, *args, _real=real, _donde=nombre, **kwargs):
            vigia.bcrypts += 1
            if any(s.in_transaction() for s in list(vigia.sesiones)):
                vigia.con_transaccion.append(f"{_donde.rsplit('.', 1)[-1]}:{func.__name__}")
            return await _real(func, *args, **kwargs)

        monkeypatch.setattr(modulo, "run_bcrypt", vigilado)
    return vigia


async def test_b2_1_sign_up_hashes_with_no_transaction_open(client: AsyncClient, vigia):
    """
    Given: Un alta con un correo libre
    When: Se registra
    Then: 201 y su bcrypt sin ninguna transacción abierta
    """
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "b21@example.com",
            "password": CLAVE,
            "first_name": "Ana",
            "last_name": "Lopez",
            "accept_terms": True,
        },
    )

    assert r.status_code == 201
    assert vigia.bcrypts >= 1
    assert vigia.con_transaccion == []


async def test_b2_1_a_taken_email_costs_the_same_bcrypt_outside_a_transaction(
    client: AsyncClient, vigia
):
    """
    Given: Un correo ya registrado
    When: Se intenta otra alta con él
    Then: El mismo 201 y el mismo bcrypt que un alta nueva (fase 3: el tiempo no dice si
          el correo existe), sin transacción abierta
    """
    datos = {
        "email": "b21.ocupado@example.com",
        "password": CLAVE,
        "first_name": "Ana",
        "last_name": "Lopez",
        "accept_terms": True,
    }
    await client.post("/api/v1/auth/register", json=datos)
    antes = vigia.bcrypts

    r = await client.post("/api/v1/auth/register", json=datos)

    assert r.status_code == 201
    assert vigia.bcrypts == antes + 1
    assert vigia.con_transaccion == []


@pytest.mark.parametrize(
    ("email", "clave", "estado"),
    [
        ("b22@example.com", CLAVE, 200),
        ("b22@example.com", "Mala$Clave123", 401),
        ("b22.nadie@example.com", CLAVE, 401),
    ],
)
async def test_b2_2_login_hashes_with_no_transaction_open(
    client: AsyncClient, vigia, email, clave, estado
):
    """
    Given: Una cuenta, y un login bueno, uno malo o con un correo que no existe
    When: Se intenta entrar
    Then: Su respuesta de siempre, y el bcrypt (también el de relleno) sin transacción abierta
    """
    await create_authenticated_user(client, "b22@example.com", CLAVE, "Ana", "Lopez")
    client.cookies.clear()
    vigia.con_transaccion.clear()
    antes = vigia.bcrypts

    r = await client.post("/api/v1/auth/login", json={"email": email, "password": clave})

    assert r.status_code == estado
    assert vigia.bcrypts > antes
    assert vigia.con_transaccion == []


async def test_b2_3_a_password_change_hashes_with_no_transaction_open(client: AsyncClient, vigia):
    """
    Given: Un usuario con sesión
    When: Cambia la contraseña
    Then: 200 y todos sus bcrypt sin transacción abierta
    """
    datos = await create_authenticated_user(client, "b23@example.com", CLAVE, "Ana", "Lopez")
    vigia.con_transaccion.clear()
    antes = vigia.bcrypts

    r = await client.patch(
        "/api/v1/users/security",
        json={"current_password": CLAVE, "new_password": NUEVA, "confirm_password": NUEVA},
        headers={"Cookie": f"access_token={datos['token']}"},
    )

    assert r.status_code == 200, r.text
    # La actual y la nueva (recién registrado, sin historial todavía)
    assert vigia.bcrypts - antes >= 2
    assert vigia.con_transaccion == []


async def test_b2_4_a_password_reset_hashes_with_no_transaction_open(client: AsyncClient, vigia):
    """
    Given: Un enlace de restablecer válido
    When: Se usa con una contraseña nueva
    Then: 200 y el bcrypt sin transacción abierta
    """
    await create_authenticated_user(client, "b24@example.com", CLAVE, "Ana", "Lopez")
    client.cookies.clear()
    await client.post("/api/v1/auth/forgot-password", json={"email": "b24@example.com"})
    # El correo sale en segundo plano (fase 3, B-2): el helper lo espera
    token = await token_de_reset_enviado("b24@example.com")
    vigia.con_transaccion.clear()
    antes = vigia.bcrypts

    r = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": NUEVA}
    )

    assert r.status_code == 200, r.text
    assert vigia.bcrypts > antes
    assert vigia.con_transaccion == []


async def test_b2_2_login_with_the_device_cookie_hashes_with_no_transaction_open(
    client: AsyncClient, vigia
):
    """
    Given: Una cuenta y la cookie de un dispositivo suyo
    When: Entra con ella (el otro camino del login)
    Then: 200 y el bcrypt sin transacción abierta
    """
    await create_authenticated_user(client, "b22.cookie@example.com", CLAVE, "Ana", "Lopez")
    client.cookies.clear()
    primero = await client.post(
        "/api/v1/auth/login", json={"email": "b22.cookie@example.com", "password": CLAVE}
    )
    (cabecera,) = [
        v
        for k, v in primero.headers.multi_items()
        if k == "set-cookie" and v.startswith("device_id=")
    ]
    client.cookies.clear()
    client.cookies.set("device_id", cabecera.split(";", 1)[0].split("=", 1)[1])
    vigia.con_transaccion.clear()
    antes = vigia.bcrypts

    r = await client.post(
        "/api/v1/auth/login", json={"email": "b22.cookie@example.com", "password": CLAVE}
    )

    assert r.status_code == 200, r.text
    assert vigia.bcrypts > antes
    assert vigia.con_transaccion == []


async def test_b2_3_an_email_only_change_hashes_with_no_transaction_open(
    client: AsyncClient, vigia
):
    """
    Given: Un usuario con sesión
    When: Pide solo cambiar el correo
    Then: 200 y un solo bcrypt (la actual), sin transacción abierta
    """
    datos = await create_authenticated_user(client, "b23.correo@example.com", CLAVE, "Ana", "Lopez")
    vigia.con_transaccion.clear()
    antes = vigia.bcrypts

    r = await client.patch(
        "/api/v1/users/security",
        json={"current_password": CLAVE, "new_email": "b23.nuevo@example.com"},
        headers={"Cookie": f"access_token={datos['token']}"},
    )

    assert r.status_code == 200, r.text
    assert vigia.bcrypts - antes == 1
    assert vigia.con_transaccion == []


async def test_b2_5_the_system_account_hashes_with_no_transaction_open(client: AsyncClient, vigia):
    """
    Given: La cuenta de sistema sin crear, con la BD real
    When: Se crea fuera de una petición
    Then: Un bcrypt y ninguna transacción abierta en ese momento
    """
    from main import app
    from src.config.dependencies import get_fabrica_de_sesiones
    from src.modules.user.application.use_cases.ensure_system_user_use_case import (
        EnsureSystemUserUseCase,
    )
    from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
        SQLAlchemyUnitOfWork,
    )

    fabrica = app.dependency_overrides[get_fabrica_de_sesiones]()
    async with fabrica() as sesion:
        vigia.sesiones.add(sesion)
        await EnsureSystemUserUseCase(SQLAlchemyUnitOfWork(sesion)).execute(
            "course.import@rydercupfriends.com"
        )

    assert vigia.bcrypts == 1
    assert vigia.con_transaccion == []
