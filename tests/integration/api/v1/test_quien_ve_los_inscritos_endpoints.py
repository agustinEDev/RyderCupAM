"""
Quién ve a los inscritos, por la API (release social 2, tabla del 27 oct 2026).

La regla la cubren los tests del servicio y de los casos de uso; aquí, que las
rutas le pasan quién mira y que «Mis competiciones» trae la privada a la que
le han invitado.
"""

import uuid
from datetime import date, timedelta
from typing import ClassVar

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


async def _jugador(client: AsyncClient, nombre: str) -> dict:
    return await create_authenticated_user(
        client, f"qvi_{nombre.lower()}@test.com", "P@ssw0rd123!", nombre, "Visible"
    )


async def _privada(client: AsyncClient, creador: dict) -> dict:
    start = date.today() + timedelta(days=30)
    return await create_competition(
        client,
        creador["cookies"],
        {
            "name": f"Privada {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 12,
            "team_assignment": "MANUAL",
            "visibility": "PRIVATE",
        },
    )


async def _mis_competiciones(client: AsyncClient, jugador: dict) -> set[str]:
    set_auth_cookies(client, jugador["cookies"])
    r = await client.get("/api/v1/competitions", params={"my_competitions": "true"})
    assert r.status_code == 200, r.text
    return {c["id"] for c in r.json()}


async def test_16_la_privada_a_la_que_le_invitan_sale_en_mis_competiciones(client: AsyncClient):
    creador = await _jugador(client, "Organiza")
    invitado = await _jugador(client, "Invitado")
    curioso = await _jugador(client, "Curioso")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert r.status_code == 201, r.text

    assert comp["id"] in await _mis_competiciones(client, invitado)
    assert comp["id"] not in await _mis_competiciones(client, curioso)


async def test_16_invitado_por_correo_antes_de_darse_de_alta(client: AsyncClient):
    """La invitación a un correo sin cuenta no tiene usuario: cuenta su correo."""
    creador = await _jugador(client, "Organizador")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations/by-email",
        json={"invitee_email": "qvi_nuevo@test.com"},
    )
    assert r.status_code == 201, r.text
    nuevo = await _jugador(client, "Nuevo")

    assert comp["id"] in await _mis_competiciones(client, nuevo)


async def _explorar(client: AsyncClient, jugador: dict, mias: str | None) -> set[str]:
    set_auth_cookies(client, jugador["cookies"])
    params = {} if mias is None else {"my_competitions": mias}
    r = await client.get("/api/v1/competitions", params=params)
    assert r.status_code == 200, r.text
    return {c["id"] for c in r.json()}


async def test_16_explorar_no_la_repite_y_todas_la_traen_tambien_por_correo(
    client: AsyncClient,
):
    """
    Revisor: ya sale en «Mis competiciones», así que explorar no la repite; y
    el listado completo la reconoce también por el correo de la invitación.
    """
    creador = await _jugador(client, "Organizadora")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations/by-email",
        json={"invitee_email": "qvi_correo@test.com"},
    )
    assert r.status_code == 201, r.text
    invitado = await _jugador(client, "Correo")

    assert comp["id"] not in await _explorar(client, invitado, "false")
    assert comp["id"] in await _explorar(client, invitado, None)
    # Filtrando por varios estados va por otro camino: también la reconoce
    set_auth_cookies(client, invitado["cookies"])
    r = await client.get("/api/v1/competitions", params={"status": ["DRAFT", "ACTIVE"]})
    assert comp["id"] in {c["id"] for c in r.json()}


async def test_17_rechazada_deja_de_salir(client: AsyncClient):
    creador = await _jugador(client, "Organizadora")
    invitado = await _jugador(client, "Invitada")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert enviada.status_code == 201, enviada.text
    set_auth_cookies(client, invitado["cookies"])
    rechazo = await client.post(
        f"/api/v1/invitations/{enviada.json()['id']}/respond", json={"action": "DECLINE"}
    )
    assert rechazo.status_code == 200, rechazo.text

    assert comp["id"] not in await _mis_competiciones(client, invitado)


class _Apunta:
    """Un caso de uso que solo apunta con qué le llaman."""

    llamadas: ClassVar[list] = []

    def __init__(self):
        type(self).llamadas = []

    async def execute(self, *args, **kwargs):
        type(self).llamadas.append(kwargs)
        raise _BastaError


class _BastaError(Exception):
    pass


async def test_14_la_agenda_sabe_quien_mira(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_get_schedule_use_case

    yo = await _jugador(client, "Mira")
    set_auth_cookies(client, yo["cookies"])
    app.dependency_overrides[get_get_schedule_use_case] = _Apunta
    try:
        # Al caso de uso solo se le pregunta con qué le llaman: lo que lanza acaba en 500
        r = await client.get(f"/api/v1/competitions/{uuid.uuid4()}/schedule")
        assert r.status_code == 500
    finally:
        app.dependency_overrides.pop(get_get_schedule_use_case, None)

    (llamada,) = _Apunta.llamadas
    assert str(llamada["viewer_id"].value) == yo["user"]["id"]
    assert llamada["viewer_is_admin"] is False
    assert llamada["viewer_email"] == "qvi_mira@test.com"


async def test_la_lista_sabe_el_correo_de_quien_mira(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_list_enrollments_use_case

    yo = await _jugador(client, "Lista")
    set_auth_cookies(client, yo["cookies"])
    app.dependency_overrides[get_list_enrollments_use_case] = _Apunta
    try:
        # Al caso de uso solo se le pregunta con qué le llaman: lo que lanza acaba en 500
        r = await client.get(f"/api/v1/competitions/{uuid.uuid4()}/enrollments")
        assert r.status_code == 500
    finally:
        app.dependency_overrides.pop(get_list_enrollments_use_case, None)

    (llamada,) = _Apunta.llamadas
    assert str(llamada["viewer_id"].value) == yo["user"]["id"]
    assert llamada["viewer_email"] == "qvi_lista@test.com"
