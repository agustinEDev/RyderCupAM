"""
El fixture `client` no suelta la base de datos con un aviso en segundo plano aún
usándola (BE #781).

El login lanza el aviso de «nuevo inicio de sesión» como una tarea del proceso, con su
propia sesión de la fábrica que el fixture sustituye (BE #737), y contesta sin
esperarla. Si el test acababa antes que la tarea, el fixture hacía `DROP DATABASE` con
su conexión aún abierta y el teardown fallaba con `ObjectInUseError` («is being
accessed by other users»), a ratos en el CI. Aquí la tarea se retrasa a propósito con
la conexión cogida: el teardown tiene que esperarla y soltar la base de datos sin error.
"""

import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.config import aviso_en_segundo_plano as avisos
from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    AvisoDeNuevoInicioDeSesion,
)
from tests.conftest import create_authenticated_user, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

CORREO = "aviso.lento@test.com"
CLAVE = "V@l1dP@ss123!"
# El aviso se suelta este tiempo DESPUÉS de empezar el teardown de `client`: sin la
# espera, el DROP de la BD llega antes con su conexión cogida, en cualquier máquina
SUELTA_TRAS_EL_TEARDOWN_S = 0.3


@pytest_asyncio.fixture
async def puerta(client: AsyncClient):
    """
    Lo que retiene el aviso. Pide `client`, así que se monta después y se desmonta
    antes que él: suelta el aviso un poco después de que empiece su teardown, nunca
    durante el test.
    """
    suelta = asyncio.Event()
    yield suelta
    asyncio.get_running_loop().call_later(SUELTA_TRAS_EL_TEARDOWN_S, suelta.set)


async def test_the_teardown_waits_for_a_sign_in_notice_still_using_the_db(
    client: AsyncClient, puerta: asyncio.Event, monkeypatch
):
    """
    Given: Un aviso de nuevo inicio de sesión bloqueado con su conexión a la BD cogida,
           que solo se suelta cuando ya ha empezado el teardown
    When: El test acaba con el aviso aún en marcha
    Then: El teardown del fixture lo espera y borra la base de datos sin error (si no,
          pytest marca ERROR en el teardown con ObjectInUseError)
    """
    en_marcha = asyncio.Event()

    async def bloqueado(self, _request):
        # Coge una conexión de la BD del test y la retiene hasta que la suelten
        await self._paises.find_all_active()
        en_marcha.set()
        await puerta.wait()

    monkeypatch.setattr(AvisoDeNuevoInicioDeSesion, "avisa", bloqueado)
    await create_authenticated_user(client, CORREO, CLAVE, "Ana", "Lenta")
    # Con el correo confirmado y sin la cookie del dispositivo, el login avisa
    await sql_en_la_bd_de_test("update users set email_verified = true where email = :e", e=CORREO)
    client.cookies.clear()

    respuesta = await client.post("/api/v1/auth/login", json={"email": CORREO, "password": CLAVE})

    assert respuesta.status_code == 200
    # El aviso ya tiene la conexión y sigue en marcha cuando el test acaba
    await asyncio.wait_for(en_marcha.wait(), timeout=5)
    en_marcha_al_acabar = [t.get_name() for t in tuple(avisos._PENDIENTES) if not t.done()]
    assert en_marcha_al_acabar == ["aviso-de-nuevo-inicio"]
