"""
Editar un campo aprobado reenviando las mismas salidas.

Las salidas nuevas de la edición tienen el mismo color y género que las viejas,
y el índice único `uq_golf_course_tees_color_gender` las rechaza si el INSERT
llega a la base de datos antes que el DELETE de las anteriores: la unidad de
trabajo de SQLAlchemy ordena los INSERT antes que los DELETE. Pasaba al editar
como administrador cambiando solo el nombre (500 en el Kind) y en su gemelo,
aprobar la propuesta de un creador que copia las salidas sobre el original.

Dos diferencias con producción esconden el fallo en la batería de siempre, y
las fixtures de abajo las quitan para estos tests:

- El índice solo existe en la migración (es funcional y parcial), y los tests
  levantan el esquema desde los metadatos.
- La sesión de los tests va con `autoflush=False` y la de producción con el
  autoflush por defecto: es el autoflush del DELETE explícito del repositorio
  el que manda antes los INSERT de las salidas nuevas.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
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
AMARILLAS = {
    "identifier": "Amarillo",
    "color": "YELLOW",
    "tee_gender": "MALE",
    "course_rating": 70.2,
    "slope_rating": 128,
    "par": 72,
}
ROJAS = {
    "identifier": "Rojo",
    "color": "RED",
    "tee_gender": "FEMALE",
    "course_rating": 71.0,
    "slope_rating": 125,
    "par": 72,
}


@pytest_asyncio.fixture(autouse=True)
async def _indices_unicos_de_produccion(client: AsyncClient) -> None:
    """Los índices únicos de las salidas, como los crea la migración ba02ec557335."""
    await sql_en_la_bd_de_test(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_golf_course_tees_color_gender "
        "ON golf_course_tees (golf_course_id, color, COALESCE(tee_gender, 'NONE')) "
        "WHERE color <> 'OTHER'"
    )
    await sql_en_la_bd_de_test(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_golf_course_tees_identifier_gender "
        "ON golf_course_tees (golf_course_id, identifier, COALESCE(tee_gender, 'NONE')) "
        "WHERE color = 'OTHER'"
    )


def _campo(nombre: str, salidas: list[dict]) -> dict:
    return {
        "name": nombre,
        "country_code": "ES",
        "course_type": "STANDARD_18",
        "tees": salidas,
        "holes": HOYOS,
    }


async def _salidas_en_bd(golf_course_id: str) -> list[tuple]:
    """Las salidas guardadas del campo, leídas de la base de datos y ordenadas."""
    resultado = await sql_en_la_bd_de_test(
        "SELECT color::text AS color, tee_gender::text AS tee_gender, identifier, "
        "course_rating, slope_rating FROM golf_course_tees WHERE golf_course_id = :id",
        id=golf_course_id,
    )
    # Ordenadas aquí: en SQL el enum del color ordena por su declaración, no por nombre
    return sorted(
        (fila.color, fila.tee_gender, fila.identifier, float(fila.course_rating), fila.slope_rating)
        for fila in resultado
    )


async def _campo_aprobado(client: AsyncClient) -> tuple[dict, dict, dict]:
    """Un administrador, un creador y un campo suyo ya aprobado con dos salidas."""
    sufijo = uuid.uuid4().hex[:8]
    admin = await create_admin_user(
        client, f"admin_salidas_{sufijo}@test.com", "AdminPass123!", "Admin", "Salidas"
    )
    creador = await create_authenticated_user(
        client, f"creador_salidas_{sufijo}@test.com", "P@ssw0rd123!", "Creador", "Salidas"
    )
    campo = await create_golf_course(
        client, creador["cookies"], _campo(f"Campo {sufijo}", [BLANCAS, AMARILLAS])
    )
    await approve_golf_course(client, admin["cookies"], campo["id"])
    return admin, creador, campo


class TestAdminEditaUnCampoAprobado:
    @pytest.mark.asyncio
    async def test_cambiar_solo_el_nombre_con_las_mismas_salidas(self, client: AsyncClient):
        """B1: solo cambia el nombre; mismas salidas → 200, nombre nuevo, mismas salidas."""
        admin, _, campo = await _campo_aprobado(client)
        antes = await _salidas_en_bd(campo["id"])

        respuesta = await client.put(
            f"/api/v1/golf-courses/{campo['id']}",
            json=_campo("Nombre nuevo", [BLANCAS, AMARILLAS]),
            cookies=admin["cookies"],
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["golf_course"]["name"] == "Nombre nuevo"
        assert respuesta.json()["pending_update"] is None
        assert await _salidas_en_bd(campo["id"]) == antes
        assert len(antes) == 2

    @pytest.mark.asyncio
    async def test_cambiar_una_salida_y_conservar_las_demas(self, client: AsyncClient):
        """B2: cambia una salida y conserva otra → queda exactamente el conjunto nuevo."""
        admin, _, campo = await _campo_aprobado(client)
        amarillas_retocadas = {**AMARILLAS, "course_rating": 69.8, "slope_rating": 126}

        respuesta = await client.put(
            f"/api/v1/golf-courses/{campo['id']}",
            json=_campo(campo["name"], [BLANCAS, amarillas_retocadas, ROJAS]),
            cookies=admin["cookies"],
        )

        assert respuesta.status_code == 200, respuesta.text
        assert await _salidas_en_bd(campo["id"]) == [
            ("RED", "FEMALE", "Rojo", 71.0, 125),
            ("WHITE", "MALE", "Blanco", 72.5, 135),
            ("YELLOW", "MALE", "Amarillo", 69.8, 126),
        ]


class TestAprobarLaPropuestaDeUnCreador:
    @pytest.mark.asyncio
    async def test_aprobar_una_propuesta_con_las_mismas_salidas(self, client: AsyncClient):
        """B3: la propuesta trae las mismas salidas → 200 y el original toma los cambios."""
        admin, creador, campo = await _campo_aprobado(client)
        propuesta = await client.put(
            f"/api/v1/golf-courses/{campo['id']}",
            json=_campo("Nombre propuesto", [BLANCAS, AMARILLAS]),
            cookies=creador["cookies"],
        )
        assert propuesta.status_code == 200, propuesta.text
        clon_id = propuesta.json()["pending_update"]["id"]
        antes = await _salidas_en_bd(campo["id"])

        respuesta = await client.put(
            f"/api/v1/golf-courses/admin/{clon_id}/approve-update", cookies=admin["cookies"]
        )

        assert respuesta.status_code == 200, respuesta.text
        actualizado = respuesta.json()["updated_golf_course"]
        assert actualizado["id"] == campo["id"]
        assert actualizado["name"] == "Nombre propuesto"
        assert actualizado["is_pending_update"] is False
        assert await _salidas_en_bd(campo["id"]) == antes


class TestCreadorEditaSuCampoAprobado:
    @pytest.mark.asyncio
    async def test_crea_una_propuesta_y_no_toca_el_original(self, client: AsyncClient):
        """B4: el creador (no admin) edita → propuesta pendiente; el original intacto."""
        _, creador, campo = await _campo_aprobado(client)
        antes = await _salidas_en_bd(campo["id"])

        respuesta = await client.put(
            f"/api/v1/golf-courses/{campo['id']}",
            json=_campo("Nombre propuesto", [BLANCAS, AMARILLAS]),
            cookies=creador["cookies"],
        )

        assert respuesta.status_code == 200, respuesta.text
        datos = respuesta.json()
        assert datos["golf_course"]["name"] == campo["name"]
        assert datos["golf_course"]["is_pending_update"] is True
        assert datos["pending_update"]["name"] == "Nombre propuesto"
        assert datos["pending_update"]["approval_status"] == "PENDING_APPROVAL"
        assert await _salidas_en_bd(campo["id"]) == antes
        assert await _salidas_en_bd(datos["pending_update"]["id"]) == antes
