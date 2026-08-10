"""
Tests E2E de perfiles y feed (BE #176).

El guard se comprueba aqui de punta a punta porque lo que importa es el **codigo
de respuesta**: un 403 delataria que la cuenta existe, asi que tiene que ser 404
y ser identico al de una cuenta inventada.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies


async def _hacerse_amigos(client: AsyncClient, a: dict, b: dict) -> None:
    """a envia solicitud, b la acepta."""
    set_auth_cookies(client, a["cookies"])
    respuesta = await client.post(
        "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
    )
    friendship_id = respuesta.json()["id"]

    set_auth_cookies(client, b["cookies"])
    await client.post(
        f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
    )


class TestPerfil:
    @pytest.mark.asyncio
    async def test_un_amigo_ve_el_perfil(self, client: AsyncClient):
        """Given dos amigos / When uno pide el perfil / Then 200 con sus datos."""
        ana = await create_authenticated_user(
            client, "perfil_a@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "perfil_b@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )
        await _hacerse_amigos(client, ana, luis)

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/profile")

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["id"] == luis["user"]["id"]
        assert datos["first_name"] == "Luis"
        assert "stats" in datos
        # El perfil de golf no lleva datos de la cuenta
        assert "email" not in datos

    @pytest.mark.asyncio
    async def test_un_desconocido_recibe_404_y_no_403(self, client: AsyncClient):
        """
        Given dos usuarios sin amistad / When uno pide el perfil / Then 404.

        Un 403 confirmaria que la cuenta existe, que es justo lo que no debe
        poder averiguarse probando identificadores.
        """
        ana = await create_authenticated_user(
            client, "perfil_c@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "perfil_d@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/profile")

        assert respuesta.status_code == 404

    @pytest.mark.asyncio
    async def test_una_cuenta_inventada_responde_igual_que_un_desconocido(
        self, client: AsyncClient
    ):
        """
        Given un id que no existe / When se pide su perfil / Then la respuesta es
        indistinguible de la de alguien que existe pero no es amigo.
        """
        ana = await create_authenticated_user(
            client, "perfil_e@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "perfil_f@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )

        set_auth_cookies(client, ana["cookies"])
        inventado = await client.get(f"/api/v1/users/{uuid4()}/profile")
        desconocido = await client.get(f"/api/v1/users/{luis['user']['id']}/profile")

        assert inventado.status_code == desconocido.status_code == 404
        assert inventado.json() == desconocido.json()

    @pytest.mark.asyncio
    async def test_requiere_autenticacion(self, client: AsyncClient):
        """Given nadie autenticado / When pide un perfil / Then 401."""
        client.cookies.clear()

        respuesta = await client.get(f"/api/v1/users/{uuid4()}/profile")

        assert respuesta.status_code == 401


class TestFeed:
    @pytest.mark.asyncio
    async def test_el_feed_llega_vacio_sin_amigos(self, client: AsyncClient):
        """Given un jugador sin amigos / When pide su feed / Then 200 y vacio."""
        ana = await create_authenticated_user(
            client, "feed_a@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get("/api/v1/users/me/feed")

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["events"] == []
        assert datos["next_cursor"] is None
        assert datos["unseen_count"] == 0

    @pytest.mark.asyncio
    async def test_marcar_el_feed_como_visto(self, client: AsyncClient):
        """Given un jugador / When marca el feed como visto / Then 204."""
        ana = await create_authenticated_user(
            client, "feed_b@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.put("/api/v1/users/me/feed/seen")

        assert respuesta.status_code == 204

    @pytest.mark.asyncio
    async def test_el_limite_de_pagina_tiene_tope(self, client: AsyncClient):
        """Given un limite desmedido / When se pide el feed / Then se rechaza."""
        ana = await create_authenticated_user(
            client, "feed_c@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get("/api/v1/users/me/feed?limit=5000")

        assert respuesta.status_code == 422


class TestActividad:
    @pytest.mark.asyncio
    async def test_la_actividad_de_un_desconocido_da_404(self, client: AsyncClient):
        """Given dos sin amistad / When se pide su actividad / Then 404, igual que el perfil."""
        ana = await create_authenticated_user(
            client, "act_a@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "act_b@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/activity")

        assert respuesta.status_code == 404

    @pytest.mark.asyncio
    async def test_un_amigo_sin_logros_devuelve_lista_vacia_no_error(
        self, client: AsyncClient
    ):
        """Given un amigo que no ha publicado nada / When se pide / Then 200 y vacio."""
        ana = await create_authenticated_user(
            client, "act_c@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "act_d@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )
        await _hacerse_amigos(client, ana, luis)

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/activity")

        assert respuesta.status_code == 200
        assert respuesta.json()["events"] == []
