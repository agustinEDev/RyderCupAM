"""
Quitar o reordenar los campos de una competición sin chocar con su orden único.

Al quitar un campo que no es el último, el dominio renumera los que quedan
(1..n sin huecos). SQLAlchemy manda los UPDATE de esa renumeración antes que el
DELETE del huérfano, y `uq_competition_golf_courses_competition_display_order`
los rechazaba: 500. Es el gemelo de las salidas de un campo.

El índice solo existe en la migración 2b72b9741fd1 y los tests levantan el
esquema desde los metadatos: la fixture de abajo lo crea igual. La sesión va
configurada como la de producción (`sesion_como_en_produccion`).
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    sql_en_la_bd_de_test,
)

pytestmark = pytest.mark.usefixtures("sesion_como_en_produccion")

HOYOS = [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)]
BLANCAS = {
    "identifier": "Blanco",
    "color": "WHITE",
    "tee_gender": "MALE",
    "course_rating": 72.5,
    "slope_rating": 135,
    "par": 72,
}


@pytest_asyncio.fixture(autouse=True)
async def _orden_unico_de_produccion(client: AsyncClient) -> None:
    """La restricción del orden por competición, como la crea la migración."""
    await sql_en_la_bd_de_test(
        "ALTER TABLE competition_golf_courses "
        "ADD CONSTRAINT uq_competition_golf_courses_competition_display_order "
        "UNIQUE (competition_id, display_order)"
    )


async def _competicion_con_campos(client: AsyncClient, cuantos: int) -> tuple[dict, dict, list]:
    """Una competición del creador con `cuantos` campos aprobados, en ese orden."""
    sufijo = uuid.uuid4().hex[:8]
    admin = await create_admin_user(
        client, f"admin_orden_{sufijo}@test.com", "AdminPass123!", "Admin", "Orden"
    )
    creador = await create_authenticated_user(
        client, f"creador_orden_{sufijo}@test.com", "P@ssw0rd123!", "Creador", "Orden"
    )
    competicion = await create_competition(client, creador["cookies"])
    campos = []
    for numero in range(1, cuantos + 1):
        campo = await create_golf_course(
            client,
            creador["cookies"],
            {
                "name": f"Campo {numero} {sufijo}",
                "country_code": "ES",
                "course_type": "STANDARD_18",
                "tees": [BLANCAS],
                "holes": HOYOS,
            },
        )
        await approve_golf_course(client, admin["cookies"], campo["id"])
        respuesta = await client.post(
            f"/api/v1/competitions/{competicion['id']}/golf-courses",
            json={"golf_course_id": campo["id"]},
            cookies=creador["cookies"],
        )
        assert respuesta.status_code in (200, 201), respuesta.text
        campos.append(campo["id"])
    return creador, competicion, campos


async def _ids_al_reves_que_el_orden(competition_id: str) -> None:
    """
    Ids que ordenan al revés que `display_order`.

    SQLAlchemy manda los UPDATE por orden de clave primaria, y los ids son
    aleatorios: así el que baja del 3 al 2 sale siempre antes que el que baja del
    2 al 1, que es el orden en que se pisan. Sin esto el test acertaría o no según
    los ids que tocasen.
    """
    await sql_en_la_bd_de_test(
        "UPDATE competition_golf_courses "
        "SET id = lpad((10 - display_order)::text, 8, '0') || '-0000-4000-8000-000000000000' "
        "WHERE competition_id = :id",
        id=competition_id,
    )


async def _orden_en_bd(competition_id: str) -> list[tuple[str, int]]:
    """(campo, orden) de la competición, leídos de la base de datos."""
    resultado = await sql_en_la_bd_de_test(
        "SELECT golf_course_id, display_order FROM competition_golf_courses "
        "WHERE competition_id = :id ORDER BY display_order",
        id=competition_id,
    )
    return [(str(fila.golf_course_id), fila.display_order) for fila in resultado]


class TestQuitarUnCampo:
    @pytest.mark.parametrize("quitado", [0, 1], ids=["el_primero", "uno_de_en_medio"])
    @pytest.mark.asyncio
    async def test_quitar_uno_que_no_es_el_ultimo_renumera_sin_huecos(
        self, client: AsyncClient, quitado: int
    ):
        """G1: quitar el primero o uno de en medio → OK y los demás quedan 1..n."""
        creador, competicion, campos = await _competicion_con_campos(client, 3)
        await _ids_al_reves_que_el_orden(competicion["id"])

        respuesta = await client.delete(
            f"/api/v1/competitions/{competicion['id']}/golf-courses/{campos[quitado]}",
            cookies=creador["cookies"],
        )

        assert respuesta.status_code == 200, respuesta.text
        quedan = [campo for i, campo in enumerate(campos) if i != quitado]
        assert await _orden_en_bd(competicion["id"]) == [(quedan[0], 1), (quedan[1], 2)]

    @pytest.mark.asyncio
    async def test_quitar_el_ultimo(self, client: AsyncClient):
        """G2: quitar el último → OK y los demás no se mueven."""
        creador, competicion, campos = await _competicion_con_campos(client, 2)

        respuesta = await client.delete(
            f"/api/v1/competitions/{competicion['id']}/golf-courses/{campos[1]}",
            cookies=creador["cookies"],
        )

        assert respuesta.status_code == 200, respuesta.text
        assert await _orden_en_bd(competicion["id"]) == [(campos[0], 1)]


class TestReordenarLosCampos:
    @pytest.mark.asyncio
    async def test_intercambiar_el_orden(self, client: AsyncClient):
        """G3: intercambiar el orden de dos campos → OK con el orden nuevo."""
        creador, competicion, campos = await _competicion_con_campos(client, 2)

        respuesta = await client.put(
            f"/api/v1/competitions/{competicion['id']}/golf-courses/reorder",
            json={"golf_course_ids": [campos[1], campos[0]]},
            cookies=creador["cookies"],
        )

        assert respuesta.status_code == 200, respuesta.text
        assert await _orden_en_bd(competicion["id"]) == [(campos[1], 1), (campos[0], 2)]
