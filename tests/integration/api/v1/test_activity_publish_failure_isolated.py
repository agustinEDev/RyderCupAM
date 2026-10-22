"""
Un fallo de base de datos al publicar en Actividad no tumba la accion (G27).

Todas las unidades de trabajo de una peticion comparten sesion. Si la
publicacion falla dentro de esa sesion, su `rollback` caduca cada objeto que
la accion ya habia guardado, y al montar la respuesta la sesion asincrona
intenta recargarlos y revienta (`MissingGreenlet`): un 500 con la accion hecha.
Por eso Actividad publica con su propia sesion.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from tests.conftest import (
    activate_competition,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
)
from tests.integration.api.v1.test_quick_match_endpoints import _create_approved_golf_course

PASSWORD = "P@ssw0rd123!"


@pytest.fixture
def feed_caido(monkeypatch):
    """
    Cualquier alta en Actividad falla en la base de datos, de verdad: la
    sentencia llega a Postgres y aborta la transaccion, como un fallo real.
    """

    async def _falla(self, events):
        if events:
            await self._session.execute(text("SELECT * FROM tabla_que_no_existe"))

    monkeypatch.setattr(SQLAlchemyActivityEventRepository, "add_many", _falla)


@pytest.mark.asyncio
@pytest.mark.usefixtures("feed_caido")
async def test_aprobar_una_solicitud_responde_bien_aunque_falle_actividad(client: AsyncClient):
    org = await create_authenticated_user(client, "iso_org@test.com", PASSWORD, "Org", "Uno")
    yo = await create_authenticated_user(client, "iso_yo@test.com", PASSWORD, "Juan", "Lopez")
    comp = await create_competition(client, org["cookies"])
    await activate_competition(client, org["cookies"], comp["id"])
    set_auth_cookies(client, yo["cookies"])
    solicitud = (await client.post(f"/api/v1/competitions/{comp['id']}/enrollments")).json()

    set_auth_cookies(client, org["cookies"])
    respuesta = await client.post(f"/api/v1/enrollments/{solicitud['id']}/approve")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["id"] == solicitud["id"]
    assert cuerpo["status"] == "APPROVED"
    assert cuerpo["user_id"] == yo["user"]["id"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("feed_caido")
async def test_terminar_una_partida_rapida_responde_bien_aunque_falle_actividad(
    client: AsyncClient,
):
    admin = await create_admin_user(client, "iso_adm@test.com", PASSWORD, "Admin", "Iso")
    yo = await create_authenticated_user(client, "iso_qm@test.com", PASSWORD, "Juan", "Lopez")
    campo = await _create_approved_golf_course(client, admin, yo)
    set_auth_cookies(client, yo["cookies"])
    partida = (
        await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": campo, "scoring_format": "STABLEFORD"},
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/quick-matches/{partida}/start", json={"scorer_ids": [yo["user"]["id"]]}
    )
    for hoyo in range(1, 19):
        # Un birdie en cada hoyo: tambien hay logros que publicar
        await client.post(f"/api/v1/quick-matches/{partida}/holes/{hoyo}/score", json={"score": 3})

    respuesta = await client.post(f"/api/v1/quick-matches/{partida}/complete")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["id"] == partida
    assert cuerpo["status"] == "COMPLETED"
