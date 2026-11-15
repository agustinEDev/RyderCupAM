"""
«Requiere tu Atención»: los hándicaps sin actualizar con la RFEG, por la API (15 nov 2026).

GET /api/v1/competitions/me/handicaps-not-updated, contra Postgres.

| Caso | Situación                                          | Respuesta                          |
|------|----------------------------------------------------|------------------------------------|
| H2   | Organizador con un español no encontrado           | as_organizer con 1 y su nombre     |
| H3   | Ese español (aquí, el propio organizador)          | as_player con la competición       |
| H5   | Actualiza su hándicap después                      | Nada                               |
| —    | Otro usuario                                       | Vacío                              |
| —    | Sin sesión                                         | 401                                |
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    OrigenActualizacion,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.sqlalchemy.handicap_update_repository import (
    SQLAlchemyHandicapUpdateRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.conftest import (
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
    sql_en_la_bd_de_test,
)

pytestmark = pytest.mark.asyncio

URL = "/api/v1/competitions/me/handicaps-not-updated"


async def _usuario(client: AsyncClient, nombre: str) -> dict:
    usuario = await create_authenticated_user(
        client, f"rfeg-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", nombre, "Pérez"
    )
    await sql_en_la_bd_de_test(
        "update users set country_code = 'ES' where id = :id", id=usuario["user"]["id"]
    )
    return usuario


async def _cerrada_con_un_no_encontrado(client: AsyncClient) -> tuple[dict, dict]:
    """Una Ryder cerrada cuyo organizador (inscrito) no encontró la RFEG."""
    organizador = await _usuario(client, "Luis")
    set_auth_cookies(client, organizador["cookies"])
    # Con hándicap, como al apuntarse (antes de que conteste la RFEG)
    puesto = await client.post(
        "/api/v1/handicaps/update-manual",
        json={"user_id": organizador["user"]["id"], "handicap": 15.0},
    )
    assert puesto.status_code == 200, puesto.text
    start = date.today() + timedelta(days=30)
    competicion = await create_competition(
        client,
        organizador["cookies"],
        {
            "name": f"Rfeg {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "tournament_type": "RYDER_CUP",
        },
    )
    cerrar = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    assert cerrar.status_code == 200, cerrar.text

    # La actualización del cierre, ya terminada: aquí no se pregunta a la RFEG
    from main import app
    from src.config.dependencies import get_fabrica_de_sesiones

    fabrica = app.dependency_overrides[get_fabrica_de_sesiones]()
    # La RFEG contesta después de que se pusiera su hándicap
    momento = datetime.now(UTC)
    actualizacion = ActualizacionDeHandicaps.crear(
        CompetitionId(uuid.UUID(competicion["id"])), OrigenActualizacion.CIERRE, momento
    )
    async with fabrica() as sesion:
        repo = SQLAlchemyHandicapUpdateRepository(sesion)
        await repo.add(actualizacion)
        await repo.apuntar(
            actualizacion.id,
            UserId(organizador["user"]["id"]),
            ResultadoRefresco.NO_ENCONTRADO,
            momento,
        )
        actualizacion.terminar(0, momento)
        await repo.update(actualizacion)
        await sesion.commit()
    return organizador, competicion


async def test_el_no_encontrado_y_su_organizador_lo_ven(client: AsyncClient):
    """
    Given una competición cerrada cuyo organizador, español e inscrito, no encontró la RFEG
    When pide lo suyo
    Then le sale como organizador (1, con su nombre) y como jugador (H2, H3)
    """
    organizador, competicion = await _cerrada_con_un_no_encontrado(client)
    set_auth_cookies(client, organizador["cookies"])

    respuesta = await client.get(URL)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["as_organizer"] == [
        {
            "competition_id": competicion["id"],
            "competition_name": competicion["name"],
            "count": 1,
            "players": [{"user_id": organizador["user"]["id"], "name": "Luis Pérez"}],
        }
    ]
    assert cuerpo["as_player"] == [
        {"competition_id": competicion["id"], "competition_name": competicion["name"]}
    ]


async def test_si_actualiza_su_handicap_desaparece(client: AsyncClient):
    """
    Given el no encontrado
    When actualiza su hándicap después (desde su perfil)
    Then ya no sale en ningún sitio (H5)
    """
    organizador, _ = await _cerrada_con_un_no_encontrado(client)
    set_auth_cookies(client, organizador["cookies"])
    actualizado = await client.post(
        "/api/v1/handicaps/update-manual",
        json={"user_id": organizador["user"]["id"], "handicap": 16.0},
    )
    assert actualizado.status_code == 200, actualizado.text

    respuesta = await client.get(URL)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"as_organizer": [], "as_player": []}


async def test_otro_usuario_no_ve_nada(client: AsyncClient):
    """Given una competición con un no encontrado When pide otro usuario Then vacío."""
    await _cerrada_con_un_no_encontrado(client)
    otro = await _usuario(client, "Eva")
    set_auth_cookies(client, otro["cookies"])

    respuesta = await client.get(URL)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"as_organizer": [], "as_player": []}


async def test_sin_sesion_es_un_401(client: AsyncClient):
    """Given nadie identificado When pide Then 401."""
    client.cookies.clear()

    respuesta = await client.get(URL)

    assert respuesta.status_code == 401, respuesta.text
