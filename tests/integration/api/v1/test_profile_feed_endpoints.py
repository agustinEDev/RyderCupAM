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
        # Entre amigos si se ve el correo: una amistad aceptada es un contacto
        # de verdad, y poder escribirle fuera de la aplicacion es parte de eso
        assert datos["email"] == luis["user"]["email"]

    @pytest.mark.asyncio
    async def test_un_desconocido_ve_la_ficha_pero_no_lo_privado(self, client: AsyncClient):
        """
        Given dos usuarios sin amistad / When uno pide el perfil / Then 200 con
        nombre, apellidos y foto, pero sin handicap ni estadisticas.
        """
        ana = await create_authenticated_user(
            client, "perfil_c@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "perfil_d@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/profile")

        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["first_name"] == "Luis"
        assert datos["is_friend"] is False
        assert datos["friendship"]["status"] == "NONE"
        assert datos["stats"] is None
        assert datos["handicap"] is None
        # El correo es de los campos privados: llega en None, no ausente
        assert datos["email"] is None
        assert luis["user"]["email"] not in respuesta.text

    @pytest.mark.asyncio
    async def test_una_cuenta_inventada_si_da_404(self, client: AsyncClient):
        """
        Given un id que no existe / When se pide su perfil / Then 404.

        El 404 se reserva para lo que de verdad no esta. Ya no sirve para ocultar
        que una cuenta existe: los jugadores se buscan por nombre, asi que su
        existencia es publica por diseño.
        """
        ana = await create_authenticated_user(
            client, "perfil_e@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{uuid4()}/profile")

        assert respuesta.status_code == 404

    @pytest.mark.asyncio
    async def test_el_perfil_dice_en_que_punto_esta_la_solicitud(self, client: AsyncClient):
        """
        Given una solicitud enviada / When miro su perfil / Then el estado lo
        refleja, para no ofrecerme mandar otra.
        """
        ana = await create_authenticated_user(
            client, "perfil_g@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "perfil_h@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )

        set_auth_cookies(client, ana["cookies"])
        await client.post("/api/v1/friends/requests", json={"addressee_id": luis["user"]["id"]})
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/profile")

        assert respuesta.json()["friendship"]["status"] == "PENDING_SENT"
        assert respuesta.json()["friendship"]["friendship_id"] is not None

    @pytest.mark.asyncio
    async def test_requiere_autenticacion(self, client: AsyncClient):
        """Given nadie autenticado / When pide un perfil / Then 401."""
        client.cookies.clear()

        respuesta = await client.get(f"/api/v1/users/{uuid4()}/profile")

        assert respuesta.status_code == 401


class TestBusqueda:
    @pytest.mark.asyncio
    async def test_la_busqueda_no_devuelve_correos(self, client: AsyncClient):
        """
        Given un jugador buscando por nombre / When encuentra a alguien / Then
        recibe nombre, apellidos y foto, nunca su correo.

        Cualquiera puede buscar por nombre, asi que lo que salga de aqui es
        publico. Devolver el correo permitia recolectar direcciones tecleando
        nombres sueltos.
        """
        await create_authenticated_user(
            client, "busca_diana@test.com", "P@ssw0rd123!", "Diana", "Buscada"
        )
        ana = await create_authenticated_user(
            client, "busca_ana@test.com", "P@ssw0rd123!", "Ana", "Buscadora"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get("/api/v1/users/search-autocomplete?query=Diana")

        assert respuesta.status_code == 200
        encontrados = respuesta.json()["users"]
        assert len(encontrados) >= 1
        for usuario in encontrados:
            assert "email" not in usuario
            assert "avatar_source" in usuario
        assert "busca_diana@test.com" not in respuesta.text


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
    async def test_la_actividad_de_un_desconocido_da_403(self, client: AsyncClient):
        """
        Given dos sin amistad / When se pide su actividad / Then 403, no 404.

        Aqui el 403 no filtra nada: el perfil de esa persona ya es visible, asi
        que su existencia no es ningun secreto. Fingir un 404 confundiria al
        cliente, que acaba de recibir su ficha.
        """
        ana = await create_authenticated_user(
            client, "act_a@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        luis = await create_authenticated_user(
            client, "act_b@test.com", "P@ssw0rd123!", "Luis", "Perez"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{luis['user']['id']}/activity")

        assert respuesta.status_code == 403

    @pytest.mark.asyncio
    async def test_la_actividad_de_una_cuenta_inventada_da_404(self, client: AsyncClient):
        """Given un id que no existe / When se pide su actividad / Then 404, no 403."""
        ana = await create_authenticated_user(
            client, "act_e@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )

        set_auth_cookies(client, ana["cookies"])
        respuesta = await client.get(f"/api/v1/users/{uuid4()}/activity")

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
