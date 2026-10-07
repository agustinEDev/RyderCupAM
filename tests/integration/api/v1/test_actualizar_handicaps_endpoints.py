"""
El botón «Actualizar hándicaps» por la API (#251, decidido el 7 oct 2026).
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    add_one_session,
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio


class _LanzadorQueApunta:
    def __init__(self):
        self.lanzadas = []

    def lanzar(self, update_id) -> None:
        self.lanzadas.append(update_id)


async def _usuario(client: AsyncClient) -> dict:
    usuario = await create_authenticated_user(
        client, f"act-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Act", "Ua"
    )
    set_auth_cookies(client, usuario["cookies"])
    respuesta = await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0},
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _cerrada(client: AsyncClient, tipo: str) -> tuple[dict, dict]:
    usuario = await _usuario(client)
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"Act {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "tournament_type": tipo,
    }
    if tipo != "RYDER_CUP":
        datos["stroke_play"] = {"category_limits": [12.0]}
    competicion = await create_competition(client, usuario["cookies"], datos)
    if tipo != "RYDER_CUP":
        await add_one_session(client, usuario["cookies"], competicion)
        set_auth_cookies(client, usuario["cookies"])
    cerrar = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    assert cerrar.status_code == 200, cerrar.text
    return usuario, competicion


def _url(competicion: dict) -> str:
    return f"/api/v1/competitions/{competicion['id']}/handicap-updates"


async def test_el_organizador_la_lanza_y_la_ficha_lo_dice(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_lanzador_de_actualizaciones

    # Cerrada sin el refresco encendido: aún no hay ninguna actualización
    _, competicion = await _cerrada(client, "RYDER_CUP")
    lanzador = _LanzadorQueApunta()
    app.dependency_overrides[get_lanzador_de_actualizaciones] = lambda: lanzador
    try:
        lanzada = await client.post(_url(competicion))
        otra = await client.post(_url(competicion))
        ficha = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()
    finally:
        app.dependency_overrides.pop(get_lanzador_de_actualizaciones, None)

    assert lanzada.status_code == 202, lanzada.text
    assert lanzada.json()["origin"] == "ORGANIZER"
    assert lanzada.json()["resumed"] is False
    # La primera sigue en curso (aquí nadie la pasa): la segunda, 409
    assert otra.status_code == 409, otra.text
    assert len(lanzador.lanzadas) == 1
    assert ficha["handicap_update"]["origin"] == "ORGANIZER"
    # La lanzada sigue en curso (aquí nadie la pasa): el botón, apagado
    assert ficha["handicap_update_window"]["open"] is False
    assert "Ya se están" in ficha["handicap_update_window"]["reason"]


async def test_sin_el_refresco_encendido_es_un_409(client: AsyncClient):
    _, competicion = await _cerrada(client, "RYDER_CUP")

    respuesta = await client.post(_url(competicion))

    assert respuesta.status_code == 409, respuesta.text


async def test_sin_zona_del_campo_no_se_sabe_cuando_sale_nadie(client: AsyncClient):
    _, competicion = await _cerrada(client, "STABLEFORD")

    respuesta = await client.post(_url(competicion))
    ficha = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()

    assert respuesta.status_code == 400, respuesta.text
    assert "zona horaria" in respuesta.json()["detail"]
    assert ficha["handicap_update_window"]["open"] is False


async def test_un_jugador_no_puede_y_no_ve_la_ventana(client: AsyncClient):
    _, competicion = await _cerrada(client, "RYDER_CUP")
    await _usuario(client)

    respuesta = await client.post(_url(competicion))
    ficha = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()

    assert respuesta.status_code == 403, respuesta.text
    assert ficha["handicap_update_window"] is None
