"""
Tests E2E de los avisos nuevos de Actividad (BE-2): que lleguen al feed desde
las acciones de verdad, y las solicitudes de amistad en el feed.

El detalle de cada aviso lo prueban los unitarios; aqui se prueba el cableado.
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    activate_competition,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
)
from tests.integration.api.v1.helpers.feed_helper import (
    hacer_privada,
    hacerse_amigos,
    insertar_eventos,
)
from tests.integration.api.v1.test_quick_match_endpoints import _create_approved_golf_course

FEED = "/api/v1/users/me/feed"
CONTADOR = "/api/v1/users/me/feed/unseen-count"
PASSWORD = "P@ssw0rd123!"


async def _tipos_del_feed(client: AsyncClient, user: dict) -> list[str]:
    set_auth_cookies(client, user["cookies"])
    respuesta = await client.get(FEED)
    assert respuesta.status_code == 200, respuesta.text
    return [e["type"] for e in respuesta.json()["events"]]


@pytest.mark.asyncio
async def test_b8_la_inscripcion_directa_en_un_publico_la_ven_los_amigos(client: AsyncClient):
    """
    B8 y A2. Given me inscribe el organizador en un torneo publico / When mi
    amigo y yo pedimos el feed / Then el ve que me he apuntado; yo, nada.
    """
    org = await create_authenticated_user(client, "be2_org@test.com", PASSWORD, "Org", "Uno")
    yo = await create_authenticated_user(client, "be2_yo@test.com", PASSWORD, "Juan", "Lopez")
    amigo = await create_authenticated_user(client, "be2_am@test.com", PASSWORD, "Eva", "Ruiz")
    await hacerse_amigos(client, yo, amigo)
    comp = await create_competition(client, org["cookies"])
    await activate_competition(client, org["cookies"], comp["id"])

    respuesta = await client.post(
        f"/api/v1/competitions/{comp['id']}/enrollments/direct",
        json={"competition_id": comp["id"], "user_id": yo["user"]["id"]},
        cookies=org["cookies"],
    )
    assert respuesta.status_code == 201, respuesta.text

    assert await _tipos_del_feed(client, amigo) == ["ENROLLED_IN_TOURNAMENT"]
    # C (22 oct): yo, «ya estas inscrito»
    assert await _tipos_del_feed(client, yo) == ["ENROLLMENT_CONFIRMED"]


async def _invitado(client: AsyncClient, prefijo: str) -> tuple[dict, str]:
    """Una competicion activa y una invitacion para mi; el id de la invitacion."""
    org = await create_authenticated_user(client, f"{prefijo}_org@test.com", PASSWORD, "Org", "Uno")
    yo = await create_authenticated_user(
        client, f"{prefijo}_yo@test.com", PASSWORD, "Juan", "Lopez"
    )
    comp = await create_competition(client, org["cookies"])
    await activate_competition(client, org["cookies"], comp["id"])
    set_auth_cookies(client, org["cookies"])
    invitada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": yo["user"]["id"]},
    )
    assert invitada.status_code == 201, invitada.text
    assert await _tipos_del_feed(client, yo) == ["INVITED_TO_TOURNAMENT"]
    set_auth_cookies(client, yo["cookies"])
    (suya,) = (await client.get("/api/v1/invitations/me")).json()["invitations"]
    return yo, suya["id"]


@pytest.mark.asyncio
async def test_c_aceptar_la_invitacion_la_retira_y_confirma(client: AsyncClient):
    """
    C (22 oct). Given una invitacion avisada / When la acepto / Then su aviso
    desaparece y llega «ya estas inscrito».
    """
    yo, invitacion = await _invitado(client, "be2c_ok")

    respuesta = await client.post(
        f"/api/v1/invitations/{invitacion}/respond", json={"action": "ACCEPT"}
    )
    assert respuesta.status_code == 200, respuesta.text

    assert await _tipos_del_feed(client, yo) == ["ENROLLMENT_CONFIRMED"]


@pytest.mark.asyncio
async def test_c_rechazar_la_invitacion_la_retira(client: AsyncClient):
    """C (22 oct). Given una invitacion avisada / When la rechazo / Then el feed queda vacio."""
    yo, invitacion = await _invitado(client, "be2c_no")

    respuesta = await client.post(
        f"/api/v1/invitations/{invitacion}/respond", json={"action": "DECLINE"}
    )
    assert respuesta.status_code == 200, respuesta.text

    assert await _tipos_del_feed(client, yo) == []


@pytest.mark.asyncio
async def test_d16_terminar_una_partida_rapida_la_publica(client: AsyncClient):
    """D16. Given una partida rapida terminada / When pido el feed / Then mi resultado."""
    admin = await create_admin_user(client, "be2_adm@test.com", PASSWORD, "Admin", "Be")
    yo = await create_authenticated_user(client, "be2_qm@test.com", PASSWORD, "Juan", "Lopez")
    campo = await _create_approved_golf_course(client, admin, yo)

    set_auth_cookies(client, yo["cookies"])
    partida = (
        await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": campo, "scoring_format": "STABLEFORD"},
        )
    ).json()["id"]
    arranque = await client.post(
        f"/api/v1/quick-matches/{partida}/start", json={"scorer_ids": [yo["user"]["id"]]}
    )
    assert arranque.status_code == 200, arranque.text
    for hoyo in range(1, 19):
        await client.post(f"/api/v1/quick-matches/{partida}/holes/{hoyo}/score", json={"score": 4})
    assert (await client.post(f"/api/v1/quick-matches/{partida}/complete")).status_code == 200

    set_auth_cookies(client, yo["cookies"])
    eventos = (await client.get(FEED)).json()["events"]
    (resultado,) = [e for e in eventos if e["type"] == "QUICK_MATCH_FINISHED"]
    assert resultado["source_match_id"] == partida
    assert resultado["payload"]["position"] is None
    assert resultado["payload"]["holes_played"] == 18


@pytest.mark.asyncio
async def test_f23_la_solicitud_recibida_sale_en_el_feed_y_cuenta(client: AsyncClient):
    """
    F23 y F26. Given Eva me pide amistad / When pedimos el feed / Then a mi me
    sale con quien la pide y cuenta; a ella, que la envio, no.
    """
    yo = await create_authenticated_user(client, "be2_f1@test.com", PASSWORD, "Juan", "Lopez")
    eva = await create_authenticated_user(client, "be2_f2@test.com", PASSWORD, "Eva", "Ruiz")
    set_auth_cookies(client, eva["cookies"])
    enviada = await client.post("/api/v1/friends/requests", json={"addressee_id": yo["user"]["id"]})
    assert enviada.status_code == 201, enviada.text

    set_auth_cookies(client, yo["cookies"])
    feed = (await client.get(FEED)).json()
    (solicitud,) = feed["pending_friend_requests"]
    assert solicitud["friendship_id"] == enviada.json()["id"]
    assert solicitud["requester"]["id"] == eva["user"]["id"]
    assert solicitud["requester"]["first_name"] == "Eva"
    assert feed["unseen_count"] == 1
    assert (await client.get(CONTADOR)).json() == {"unseen_count": 1}

    set_auth_cookies(client, eva["cookies"])
    assert (await client.get(FEED)).json()["pending_friend_requests"] == []


@pytest.mark.asyncio
async def test_e22_cada_evento_lleva_su_clave_de_tarjeta(client: AsyncClient):
    """E22. Given un logro / When pido el feed / Then lleva `group_key`."""
    yo = await create_authenticated_user(client, "be2_g1@test.com", PASSWORD, "Juan", "Lopez")
    await insertar_eventos(yo["user"]["id"], [datetime(2026, 9, 14, 18, 0) + timedelta(hours=1)])

    set_auth_cookies(client, yo["cookies"])
    (evento,) = (await client.get(FEED)).json()["events"]

    assert evento["group_key"] == f"{yo['user']['id']}:{evento['source_match_id']}"


@pytest.mark.asyncio
async def test_e_un_torneo_que_ahora_es_privado_no_sale_aunque_quede_su_aviso(
    client: AsyncClient,
):
    """
    E (22 oct). Given mi amigo apuntado a dos torneos publicos y uno pasa a
    privado sin que se borre su aviso / When pido el feed y su actividad /
    Then solo sale el del que sigue publico.
    """
    org = await create_authenticated_user(client, "be2e_org@test.com", PASSWORD, "Org", "Uno")
    yo = await create_authenticated_user(client, "be2e_yo@test.com", PASSWORD, "Juan", "Lopez")
    amigo = await create_authenticated_user(client, "be2e_am@test.com", PASSWORD, "Eva", "Ruiz")
    await hacerse_amigos(client, yo, amigo)
    privada = await create_competition(client, org["cookies"])
    publica = await create_competition(client, org["cookies"])
    ahora = datetime.now().replace(microsecond=0)
    for minuto, comp in ((1, privada), (2, publica)):
        await insertar_eventos(
            amigo["user"]["id"],
            [ahora + timedelta(minutes=minuto)],
            tipo="ENROLLED_IN_TOURNAMENT",
            payload={"competition_id": comp["id"], "competition_name": comp["name"]},
            source_match_id=comp["id"],
        )
    await hacer_privada(privada["id"])

    set_auth_cookies(client, yo["cookies"])
    feed = (await client.get(FEED)).json()["events"]
    actividad = (await client.get(f"/api/v1/users/{amigo['user']['id']}/activity")).json()

    assert [e["payload"]["competition_id"] for e in feed] == [publica["id"]]
    assert [e["payload"]["competition_id"] for e in actividad["events"]] == [publica["id"]]


@pytest.mark.asyncio
async def test_cerrar_la_inscripcion_retira_el_aviso_de_invitado(client: AsyncClient):
    """
    Agustin, 22 oct. Given una invitacion avisada / When el organizador cierra
    la inscripcion y la invitacion se queda sin plaza / Then su aviso desaparece.
    """
    org = await create_authenticated_user(client, "be2nr_org@test.com", PASSWORD, "Org", "Uno")
    yo = await create_authenticated_user(client, "be2nr_yo@test.com", PASSWORD, "Juan", "Lopez")
    comp = await create_competition(client, org["cookies"])
    await activate_competition(client, org["cookies"], comp["id"])
    set_auth_cookies(client, org["cookies"])
    invitada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": yo["user"]["id"]},
    )
    assert invitada.status_code == 201, invitada.text
    assert await _tipos_del_feed(client, yo) == ["INVITED_TO_TOURNAMENT"]

    set_auth_cookies(client, org["cookies"])
    cerrada = await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
    assert cerrada.status_code == 200, cerrada.text

    assert await _tipos_del_feed(client, yo) == []
