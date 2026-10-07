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


async def test_un_administrador_tambien_puede(client: AsyncClient):
    """Pendiente de la #509 (CodeRabbit): el caso del administrador, por la API."""
    from main import app
    from src.config.dependencies import get_lanzador_de_actualizaciones
    from tests.conftest import create_admin_user

    _, competicion = await _cerrada(client, "RYDER_CUP")
    admin = await create_admin_user(
        client, f"adm-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Ad", "Min"
    )
    set_auth_cookies(client, admin["cookies"])
    app.dependency_overrides[get_lanzador_de_actualizaciones] = _LanzadorQueApunta
    try:
        respuesta = await client.post(_url(competicion))
    finally:
        app.dependency_overrides.pop(get_lanzador_de_actualizaciones, None)

    assert respuesta.status_code == 202, respuesta.text


async def test_programar_verla_en_la_ficha_y_anularla(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_lanzador_de_actualizaciones

    _, competicion = await _cerrada(client, "RYDER_CUP")
    para = "2099-01-01T03:00:00+00:00"
    app.dependency_overrides[get_lanzador_de_actualizaciones] = _LanzadorQueApunta
    try:
        programada = await client.put(f"{_url(competicion)}/schedule", json={"run_at": para})
        ficha = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()
        anulada = await client.delete(f"{_url(competicion)}/schedule")
        despues = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()
    finally:
        app.dependency_overrides.pop(get_lanzador_de_actualizaciones, None)

    assert programada.status_code == 200, programada.text
    assert ficha["handicap_update_window"]["scheduled_at"].startswith("2099-01-01T03:00:00")
    assert anulada.status_code == 204, anulada.text
    assert despues["handicap_update_window"]["scheduled_at"] is None


async def test_programar_sin_huso_es_un_422_y_sin_refresco_un_409(client: AsyncClient):
    _, competicion = await _cerrada(client, "RYDER_CUP")

    sin_huso = await client.put(
        f"{_url(competicion)}/schedule", json={"run_at": "2099-01-01T03:00:00"}
    )
    sin_refresco = await client.put(
        f"{_url(competicion)}/schedule", json={"run_at": "2099-01-01T03:00:00Z"}
    )

    assert sin_huso.status_code == 422, sin_huso.text
    assert sin_refresco.status_code == 409, sin_refresco.text
