"""
El hándicap de un Stableford o un Medal, por la API (#251, decidido el 7 oct 2026).

Como la RFEG: sin hándicap no se entra, se fija al cerrar las inscripciones y es
el de todo el torneo. El organizador puede poner uno personalizado, hasta cerrar,
y nunca dejar a nadie sin ninguno. La lista de inscritos da el hándicap fijado y
la categoría desde el cierre.
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


def _datos(**extra) -> dict:
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"Medal {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "tournament_type": "STABLEFORD",
        "stroke_play": {"category_limits": [12.0]},
    }
    datos.update(extra)
    return datos


async def _usuario(client: AsyncClient, handicap: float | None = None) -> dict:
    usuario = await create_authenticated_user(
        client, f"fij-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Fija", "Do"
    )
    set_auth_cookies(client, usuario["cookies"])
    if handicap is not None:
        respuesta = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": usuario["user"]["id"], "manual_handicap": handicap},
        )
        assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _inscritos(client: AsyncClient, competicion: dict) -> list[dict]:
    respuesta = await client.get(f"/api/v1/competitions/{competicion['id']}/enrollments")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


async def test_sin_handicap_no_se_puede_crear_un_stableford(client: AsyncClient):
    await _usuario(client)

    respuesta = await client.post("/api/v1/competitions", json=_datos())

    assert respuesta.status_code == 400, respuesta.text
    assert "hándicap" in respuesta.json()["detail"]


async def test_al_cerrar_se_fija_y_la_lista_da_la_categoria(client: AsyncClient):
    usuario = await _usuario(client, handicap=14.2)
    competicion = await create_competition(client, usuario["cookies"], _datos())

    antes = (await _inscritos(client, competicion))[0]
    cerrar = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    despues = (await _inscritos(client, competicion))[0]

    assert cerrar.status_code == 200, cerrar.text
    assert (antes["fixed_handicap"], antes["category"]) == (None, None)
    assert float(despues["fixed_handicap"]) == 14.2
    # Un solo jugador: con menos de 6, las dos categorías se juntan en una
    assert despues["category"] == 1


async def test_con_las_inscripciones_cerradas_no_se_toca_el_personalizado(client: AsyncClient):
    usuario = await _usuario(client, handicap=14.2)
    competicion = await create_competition(client, usuario["cookies"], _datos())
    (inscripcion,) = await _inscritos(client, competicion)
    await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")

    respuesta = await client.put(
        f"/api/v1/enrollments/{inscripcion['id']}/handicap",
        json={"enrollment_id": inscripcion["id"], "custom_handicap": 9.0},
    )

    assert respuesta.status_code == 400, respuesta.text


async def test_iniciar_no_vuelve_a_fijar(client: AsyncClient):
    usuario = await _usuario(client, handicap=14.2)
    competicion = await create_competition(client, usuario["cookies"], _datos())
    await add_one_session(client, usuario["cookies"], competicion)
    set_auth_cookies(client, usuario["cookies"])
    await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 2.0},
    )

    iniciar = await client.post(f"/api/v1/competitions/{competicion['id']}/start")
    (inscrito,) = await _inscritos(client, competicion)

    assert iniciar.status_code == 200, iniciar.text
    assert float(inscrito["fixed_handicap"]) == 14.2


async def test_en_una_ryder_nada_de_esto(client: AsyncClient):
    usuario = await _usuario(client)
    competicion = await create_competition(
        client, usuario["cookies"], _datos(tournament_type="RYDER_CUP", stroke_play=None)
    )
    await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")

    (inscrito,) = await _inscritos(client, competicion)

    assert (inscrito["fixed_handicap"], inscrito["category"]) == (None, None)


async def test_no_se_deja_a_nadie_sin_handicap(client: AsyncClient):
    """Quitarle el personalizado a quien no tiene en su perfil: 400, no 500."""
    jugador = await _usuario(client)  # sin hándicap
    organizador = await _usuario(client, handicap=14.2)
    competicion = await create_competition(client, organizador["cookies"], _datos())
    set_auth_cookies(client, organizador["cookies"])

    sin_personalizado = await client.post(
        f"/api/v1/competitions/{competicion['id']}/enrollments/direct",
        json={"competition_id": competicion["id"], "user_id": jugador["user"]["id"]},
    )
    con_personalizado = await client.post(
        f"/api/v1/competitions/{competicion['id']}/enrollments/direct",
        json={
            "competition_id": competicion["id"],
            "user_id": jugador["user"]["id"],
            "custom_handicap": 18.0,
        },
    )
    quitar = await client.delete(f"/api/v1/enrollments/{con_personalizado.json()['id']}/handicap")

    assert sin_personalizado.status_code == 400, sin_personalizado.text
    assert con_personalizado.status_code in (200, 201), con_personalizado.text
    assert quitar.status_code == 400, quitar.text
    assert "sin hándicap" in quitar.json()["detail"]


class _LanzadorQueApunta:
    """Apunta lo que se lanzaría; la pasada de verdad tiene sus propios tests."""

    def __init__(self):
        self.lanzadas = []

    def lanzar(self, update_id) -> None:
        self.lanzadas.append(update_id)


async def test_al_cerrar_la_ficha_ensena_al_organizador_quien_falta(client: AsyncClient):
    """Con el refresco encendido, al cerrar se lanza y el organizador ve quién falta."""
    from main import app
    from src.config.dependencies import get_lanzador_de_actualizaciones

    lanzador = _LanzadorQueApunta()
    app.dependency_overrides[get_lanzador_de_actualizaciones] = lambda: lanzador
    try:
        jugador = await _usuario(client, handicap=20.0)
        organizador = await _usuario(client, handicap=14.2)
        competicion = await create_competition(client, organizador["cookies"], _datos())
        set_auth_cookies(client, organizador["cookies"])
        await client.post(
            f"/api/v1/competitions/{competicion['id']}/enrollments/direct",
            json={"competition_id": competicion["id"], "user_id": jugador["user"]["id"]},
        )
        cerrar = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")

        ficha = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()
        set_auth_cookies(client, jugador["cookies"])
        ficha_del_jugador = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()
    finally:
        app.dependency_overrides.pop(get_lanzador_de_actualizaciones, None)

    assert cerrar.status_code == 200, cerrar.text
    assert len(lanzador.lanzadas) == 1
    estado = ficha["handicap_update"]
    assert (estado["status"], estado["origin"]) == ("IN_PROGRESS", "ENROLLMENTS_CLOSED")
    assert {p["user_id"] for p in estado["pending_players"]} == {
        organizador["user"]["id"],
        jugador["user"]["id"],
    }
    assert ficha_del_jugador["handicap_update"] is None


async def test_sin_el_refresco_encendido_no_hay_actualizacion(client: AsyncClient):
    """En los tests (y fuera de producción) al cerrar no se pregunta a la RFEG."""
    usuario = await _usuario(client, handicap=14.2)
    competicion = await create_competition(client, usuario["cookies"], _datos())

    await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    ficha = (await client.get(f"/api/v1/competitions/{competicion['id']}")).json()

    assert ficha["handicap_update"] is None
