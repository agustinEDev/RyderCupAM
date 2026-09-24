"""
Sin género no se entra en una competición (#710, 24 sep).

Las barras se valoran por género: sin él, al generar los partidos se bloqueaba
la sesión entera. Se exige al entrar, y quien lo tiene no nota nada.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


class TestElGeneroParaApuntarse:
    async def test_sin_genero_pedir_plaza_es_400_y_dice_que_hacer(self, client: AsyncClient):
        creador = await create_authenticated_user(
            client, "gp_creator@test.com", "P@ssw0rd123!", "Creator", "Genero"
        )
        sin_genero = await create_authenticated_user(
            client, "gp_none@test.com", "P@ssw0rd123!", "Nadie", "Genero", gender=None
        )
        comp = await create_competition(client, creador["cookies"])
        set_auth_cookies(client, sin_genero["cookies"])

        respuesta = await client.post(f"/api/v1/competitions/{comp['id']}/enrollments")

        assert respuesta.status_code == 400, respuesta.text
        assert "género en tu perfil" in respuesta.json()["detail"]

    async def test_el_organizador_tampoco_lo_inscribe_sin_genero(self, client: AsyncClient):
        creador = await create_authenticated_user(
            client, "gp_creator2@test.com", "P@ssw0rd123!", "Creator", "Genero"
        )
        sin_genero = await create_authenticated_user(
            client, "gp_none2@test.com", "P@ssw0rd123!", "Nadie", "Genero", gender=None
        )
        comp = await create_competition(client, creador["cookies"])
        set_auth_cookies(client, creador["cookies"])

        respuesta = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"competition_id": comp["id"], "user_id": sin_genero["user"]["id"]},
        )

        assert respuesta.status_code == 400, respuesta.text
        assert "no tiene el género" in respuesta.json()["detail"]

    async def test_con_genero_no_se_nota_nada(self, client: AsyncClient):
        creador = await create_authenticated_user(
            client, "gp_creator3@test.com", "P@ssw0rd123!", "Creator", "Genero"
        )
        con_genero = await create_authenticated_user(
            client, "gp_yes@test.com", "P@ssw0rd123!", "Alguien", "Genero", gender="FEMALE"
        )
        comp = await create_competition(client, creador["cookies"])
        set_auth_cookies(client, con_genero["cookies"])

        respuesta = await client.post(f"/api/v1/competitions/{comp['id']}/enrollments")

        assert respuesta.status_code in (200, 201), respuesta.text
