"""
Las rutas de los sobres, montadas de verdad (FE #655).

Lo que un test unitario no ve: que las tres rutas existen, que la inyección de
dependencias monta el Unit of Work **con su repositorio de sobres** —en la sala
de draft eso faltaba y solo lo vio la integración— y que la sesión y el CSRF
dejan pasar.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = [pytest.mark.asyncio]


class TestLasRutasDeLosSobres:
    async def test_una_sesion_que_no_existe_responde_404_y_no_revienta(self, client: AsyncClient):
        """Con la UoW mal montada esto sería un 500, no un 404."""
        usuario = await create_authenticated_user(
            client, "sobres-1@test.com", "P@ssw0rd123!", "Sobres", "Uno"
        )
        set_auth_cookies(client, usuario["cookies"])

        respuesta = await client.get(f"/api/v1/competitions/rounds/{uuid4()}/envelopes")

        assert respuesta.status_code == 404, respuesta.text

    async def test_entregar_en_una_sesion_que_no_existe_tambien(self, client: AsyncClient):
        usuario = await create_authenticated_user(
            client, "sobres-2@test.com", "P@ssw0rd123!", "Sobres", "Dos"
        )
        set_auth_cookies(client, usuario["cookies"])

        respuesta = await client.put(
            f"/api/v1/competitions/rounds/{uuid4()}/envelope",
            json={"entries": [[str(uuid4())]]},
        )

        assert respuesta.status_code == 404, respuesta.text

    async def test_abrirlos_en_una_sesion_que_no_existe_tambien(self, client: AsyncClient):
        usuario = await create_authenticated_user(
            client, "sobres-3@test.com", "P@ssw0rd123!", "Sobres", "Tres"
        )
        set_auth_cookies(client, usuario["cookies"])

        respuesta = await client.post(f"/api/v1/competitions/rounds/{uuid4()}/envelopes/reveal")

        assert respuesta.status_code == 404, respuesta.text

    async def test_sin_sesion_no_se_entrega_nada(self, client: AsyncClient):
        client.cookies.clear()

        respuesta = await client.put(
            f"/api/v1/competitions/rounds/{uuid4()}/envelope",
            json={"entries": [[str(uuid4())]]},
        )

        assert respuesta.status_code in (401, 403), respuesta.text
