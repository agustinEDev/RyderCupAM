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


async def test_las_partidas_saben_el_correo_de_quien_mira(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_ver_partidas_use_case

    yo = await _jugador(client, "Partidas")
    set_auth_cookies(client, yo["cookies"])
    app.dependency_overrides[get_ver_partidas_use_case] = _Apunta
    try:
        r = await client.get(f"/api/v1/competitions/rounds/{uuid.uuid4()}/groups")
        assert r.status_code == 500
    finally:
        app.dependency_overrides.pop(get_ver_partidas_use_case, None)

    (llamada,) = _Apunta.llamadas
    assert llamada["email"] == "qvi_partidas@test.com"


# /code-review del front: la ficha dice qué ve cada uno de los inscritos, para
# no adivinarlo comparando la lista con el número
async def _visibilidad(client: AsyncClient, jugador: dict, comp: dict) -> str:
    set_auth_cookies(client, jugador["cookies"])
    r = await client.get(f"/api/v1/competitions/{comp['id']}")
    assert r.status_code == 200, r.text
    return r.json()["enrolled_visibility"]


async def test_la_ficha_dice_que_ve_cada_uno(client: AsyncClient):
    creador = await _jugador(client, "Ficha")
    invitado = await _jugador(client, "Fichado")
    curioso = await _jugador(client, "Mirona")
    privada = await _privada(client, creador)
    publica = await create_competition(client, creador["cookies"])
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        f"/api/v1/competitions/{privada['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert r.status_code == 201, r.text

    assert await _visibilidad(client, creador, privada) == "ALL"
    assert await _visibilidad(client, invitado, privada) == "FRIENDS"
    assert await _visibilidad(client, curioso, privada) == "NONE"
    assert await _visibilidad(client, curioso, publica) == "FRIENDS"


# Aceptar desde la ficha (tabla del 27 oct 2026, filas 13-16): la ficha trae
# la invitación pendiente de quien mira, con su id y cuándo caduca
async def _pendiente(client: AsyncClient, jugador: dict, comp: dict):
    set_auth_cookies(client, jugador["cookies"])
    r = await client.get(f"/api/v1/competitions/{comp['id']}")
    assert r.status_code == 200, r.text
    return r.json()["my_pending_invitation"]


async def test_13_la_ficha_trae_la_invitacion_pendiente_de_quien_mira(client: AsyncClient):
    creador = await _jugador(client, "Anfitrion")
    invitado = await _jugador(client, "Huesped")
    curioso = await _jugador(client, "Ajeno")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert enviada.status_code == 201, enviada.text

    suya = await _pendiente(client, invitado, comp)

    assert suya["id"] == enviada.json()["id"]
    assert suya["expires_at"]
    assert await _pendiente(client, curioso, comp) is None
    assert await _pendiente(client, creador, comp) is None


async def test_13_tambien_la_que_se_mando_a_su_correo_antes_del_alta(client: AsyncClient):
    creador = await _jugador(client, "Anfitriona")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations/by-email",
        json={"invitee_email": "qvi_huespeda@test.com"},
    )
    assert enviada.status_code == 201, enviada.text
    nueva = await _jugador(client, "Huespeda")

    assert (await _pendiente(client, nueva, comp))["id"] == enviada.json()["id"]


async def test_15_tras_rechazarla_ya_no_hay_pendiente(client: AsyncClient):
    creador = await _jugador(client, "Anfitriondos")
    invitado = await _jugador(client, "Huespeddos")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    set_auth_cookies(client, invitado["cookies"])
    r = await client.post(
        f"/api/v1/invitations/{enviada.json()['id']}/respond", json={"action": "DECLINE"}
    )
    assert r.status_code == 200, r.text

    assert await _pendiente(client, invitado, comp) is None


async def test_13_un_admin_invitado_tambien_la_ve_para_aceptarla(client: AsyncClient):
    """Un admin también juega: si le invitan, acepta desde la ficha como cualquiera."""
    from tests.conftest import create_admin_user

    creador = await _jugador(client, "Organizadorx")
    admin = await create_admin_user(
        client, f"qvi_admin_{uuid.uuid4().hex[:6]}@test.com", "P@ssw0rd123!", "Admin", "Jugador"
    )
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": admin["user"]["id"]},
    )
    assert enviada.status_code == 201, enviada.text

    assert (await _pendiente(client, admin, comp))["id"] == enviada.json()["id"]


async def _invita(client: AsyncClient, creador: dict, comp: dict, invitado: dict) -> dict:
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert enviada.status_code == 201, enviada.text
    return enviada.json()


async def test_13_ya_inscrito_a_mano_no_le_ofrece_aceptar(client: AsyncClient):
    """Revisor: aceptarla daría 400 («ya tiene inscripción»)."""
    creador = await _jugador(client, "Organizadory")
    invitado = await _jugador(client, "Inscritoamano")
    comp = await _privada(client, creador)
    await _invita(client, creador, comp, invitado)
    set_auth_cookies(client, creador["cookies"])
    directa = await client.post(
        f"/api/v1/competitions/{comp['id']}/enrollments/direct",
        json={"competition_id": comp["id"], "user_id": invitado["user"]["id"]},
    )
    assert directa.status_code in (200, 201), directa.text

    assert await _pendiente(client, invitado, comp) is None


async def test_13_cancelada_no_le_ofrece_aceptar(client: AsyncClient):
    """Revisor: solo se acepta en una competición activa."""
    creador = await _jugador(client, "Organizadorz")
    invitado = await _jugador(client, "Invitadocancelado")
    comp = await _privada(client, creador)
    await _invita(client, creador, comp, invitado)
    set_auth_cookies(client, creador["cookies"])
    cancelada = await client.post(f"/api/v1/competitions/{comp['id']}/cancel", json={})
    assert cancelada.status_code == 200, cancelada.text

    assert await _pendiente(client, invitado, comp) is None


async def test_16_caducada_no_sale(client: AsyncClient):
    from sqlalchemy import text

    from main import app
    from src.config.dependencies import get_db_session

    creador = await _jugador(client, "Organizadorw")
    invitado = await _jugador(client, "Invitadocaducado")
    comp = await _privada(client, creador)
    enviada = await _invita(client, creador, comp, invitado)
    async for session in app.dependency_overrides[get_db_session]():
        try:
            await session.execute(
                text(
                    "UPDATE invitations SET expires_at = now() - interval '1 minute' WHERE id = :id"
                ),
                {"id": enviada["id"]},
            )
            await session.commit()
            break
        finally:
            await session.close()

    assert await _pendiente(client, invitado, comp) is None
