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
from httpx import AsyncClient

from src.modules.user.application.services.aviso_de_nuevo_inicio_de_sesion import (
    AvisoDeNuevoInicioDeSesion,
)
from tests.conftest import create_authenticated_user
from tests.integration.api.v1.test_sesion_desactivada_y_codigos import _sql

pytestmark = pytest.mark.asyncio

CORREO = "aviso.lento@test.com"
CLAVE = "V@l1dP@ss123!"
RETRASO_S = 0.5


async def test_the_teardown_waits_for_a_sign_in_notice_still_using_the_db(
    client: AsyncClient, monkeypatch
):
    """
    Given: Un aviso de nuevo inicio de sesión que tarda, con su conexión a la BD cogida
    When: El test acaba con el aviso aún en marcha
    Then: El teardown del fixture lo espera y borra la base de datos sin error (si no,
          pytest marca ERROR en el teardown con ObjectInUseError)
    """
    en_marcha = asyncio.Event()
    original = AvisoDeNuevoInicioDeSesion.avisa

    async def lento(self, request):
        # Coge una conexión de la BD del test y la retiene, como un aviso lento
        await self._paises.find_all_active()
        en_marcha.set()
        await asyncio.sleep(RETRASO_S)
        await original(self, request)

    monkeypatch.setattr(AvisoDeNuevoInicioDeSesion, "avisa", lento)
    await create_authenticated_user(client, CORREO, CLAVE, "Ana", "Lenta")
    # Con el correo confirmado y sin la cookie del dispositivo, el login avisa
    await _sql("update users set email_verified = true where email = :e", e=CORREO)
    client.cookies.clear()

    respuesta = await client.post("/api/v1/auth/login", json={"email": CORREO, "password": CLAVE})

    assert respuesta.status_code == 200
    # El aviso ya tiene la conexión y sigue en marcha cuando el test acaba
    await asyncio.wait_for(en_marcha.wait(), timeout=5)
