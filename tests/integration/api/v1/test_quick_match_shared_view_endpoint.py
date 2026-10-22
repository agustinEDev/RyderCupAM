"""
GET /api/v1/quick-matches/{id}/shared: la partida rapida de un amigo, en solo
lectura (bloque K, 22 oct 2026).

Los casos finos (bloqueos, papelera, cuentas desactivadas) estan en los
unitarios del caso de uso; aqui, el contrato HTTP y que la ruta normal no cambia.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_golf_course,
    set_auth_cookies,
)

PASSWORD = "P@ssw0rd123!"


async def _make_friends(client: AsyncClient, a: dict, b: dict) -> None:
    set_auth_cookies(client, a["cookies"])
    sent = await client.post("/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]})
    assert sent.status_code == 201, sent.text
    set_auth_cookies(client, b["cookies"])
    accepted = await client.post(
        f"/api/v1/friends/requests/{sent.json()['id']}/respond", json={"action": "ACCEPT"}
    )
    assert accepted.status_code == 200, accepted.text


async def _user(client: AsyncClient, email: str, first_name: str) -> dict:
    return await create_authenticated_user(client, email, PASSWORD, first_name, "Test")


async def _match(
    client: AsyncClient, prefix: str, *, players: int = 1, complete: bool = True
) -> tuple[dict, str]:
    """Ana crea un stableford con `players` amigos suyos y un invitado, y lo termina."""
    admin = await create_admin_user(client, f"{prefix}_admin@test.com", PASSWORD, "Admin", "Xavi")
    ana = await _user(client, f"{prefix}_ana@test.com", "Ana")
    course = await create_golf_course(client, ana["cookies"])
    await approve_golf_course(client, admin["cookies"], course["id"])

    amigos = []
    for i in range(players):
        amigo = await _user(client, f"{prefix}_p{i}@test.com", ("Bea", "Carlos", "Dani")[i])
        await _make_friends(client, ana, amigo)
        amigos.append(amigo)

    set_auth_cookies(client, ana["cookies"])
    created = await client.post(
        "/api/v1/quick-matches",
        json={"golf_course_id": course["id"], "scoring_format": "STABLEFORD"},
    )
    assert created.status_code == 201, created.text
    match_id = created.json()["id"]
    for amigo in amigos:
        added = await client.post(
            f"/api/v1/quick-matches/{match_id}/participants",
            json={"friend_user_id": amigo["user"]["id"]},
        )
        assert added.status_code == 201, added.text
    if players < 3:
        guest = await client.post(
            f"/api/v1/quick-matches/{match_id}/participants/guest",
            json={"first_name": "Jane", "last_name": "Doe", "handicap": 18.4},
        )
        assert guest.status_code == 201, guest.text
    started = await client.post(
        f"/api/v1/quick-matches/{match_id}/start", json={"scorer_ids": [ana["user"]["id"]]}
    )
    assert started.status_code == 200, started.text
    scored = await client.post(f"/api/v1/quick-matches/{match_id}/holes/1/score", json={"score": 4})
    assert scored.status_code == 200, scored.text
    if complete:
        done = await client.post(f"/api/v1/quick-matches/{match_id}/complete")
        assert done.status_code == 200, done.text
    return ana, match_id


@pytest.mark.asyncio
async def test_a_friend_reads_the_finished_match(client: AsyncClient):
    ana, match_id = await _match(client, "qms_ok")
    viewer = await _user(client, "qms_ok_viewer@test.com", "Viewer")
    await _make_friends(client, viewer, ana)

    set_auth_cookies(client, viewer["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["read_only"] is True
    assert body["viewer_is_participant"] is False
    assert body["status"] == "COMPLETED"
    assert [(h["hole_number"], h["score"]) for h in body["hole_scores"]] == [(1, 4)]
    nombres = {p["is_guest"]: p["name"] for p in body["participants"] if p["name"] or p["is_guest"]}
    assert nombres[True] is None
    ana_dto = next(p for p in body["participants"] if p["user_id"] == ana["user"]["id"])
    assert ana_dto["name"] == "Ana Test"


@pytest.mark.asyncio
async def test_the_regular_detail_stays_participant_only(client: AsyncClient):
    ana, match_id = await _match(client, "qms_regular")
    viewer = await _user(client, "qms_regular_viewer@test.com", "Viewer")
    await _make_friends(client, viewer, ana)

    set_auth_cookies(client, viewer["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_participant_reads_it_with_every_name(client: AsyncClient):
    ana, match_id = await _match(client, "qms_part")

    set_auth_cookies(client, ana["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["viewer_is_participant"] is True
    assert next(p for p in body["participants"] if p["is_guest"])["name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_a_stranger_gets_403(client: AsyncClient):
    _ana, match_id = await _match(client, "qms_stranger")
    stranger = await _user(client, "qms_stranger_x@test.com", "Stranger")

    set_auth_cookies(client, stranger["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_match_in_progress_gets_403(client: AsyncClient):
    ana, match_id = await _match(client, "qms_live", complete=False)
    viewer = await _user(client, "qms_live_viewer@test.com", "Viewer")
    await _make_friends(client, viewer, ana)

    set_auth_cookies(client, viewer["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_participant_of_a_match_in_progress_gets_200(client: AsyncClient):
    """Arreglo del 22 oct: el cliente lo lleva a su anotacion con `viewer_is_participant`."""
    ana, match_id = await _match(client, "qms_live_part", complete=False)

    set_auth_cookies(client, ana["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["viewer_is_participant"] is True
    assert body["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_sharing_off_gets_403(client: AsyncClient):
    ana, match_id = await _match(client, "qms_off")
    viewer = await _user(client, "qms_off_viewer@test.com", "Viewer")
    await _make_friends(client, viewer, ana)
    set_auth_cookies(client, ana["cookies"])
    off = await client.put("/api/v1/social/activity-sharing", json={"enabled": False})
    assert off.status_code == 200, off.text

    set_auth_cookies(client, viewer["cookies"])
    response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_match_is_404(client: AsyncClient):
    viewer = await _user(client, "qms_404_viewer@test.com", "Viewer")

    set_auth_cookies(client, viewer["cookies"])
    response = await client.get("/api/v1/quick-matches/00000000-0000-4000-8000-000000000000/shared")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_without_session_is_401(client: AsyncClient):
    client.cookies.clear()
    response = await client.get("/api/v1/quick-matches/00000000-0000-4000-8000-000000000000/shared")

    assert response.status_code == 401


async def _statements(client: AsyncClient, viewer: dict, match_id: str) -> int:
    sentencias: list[str] = []

    def _cuenta(conn, cursor, statement, *args):
        sentencias.append(statement)

    set_auth_cookies(client, viewer["cookies"])
    event.listen(Engine, "before_cursor_execute", _cuenta)
    try:
        response = await client.get(f"/api/v1/quick-matches/{match_id}/shared")
    finally:
        event.remove(Engine, "before_cursor_execute", _cuenta)
    assert response.status_code == 200, response.text
    return len(sentencias)


@pytest.mark.asyncio
async def test_same_queries_with_two_or_four_players(client: AsyncClient):
    """Sin N+1: cuatro jugadores con cuenta cuestan lo mismo que dos."""
    ana_two, two = await _match(client, "qms_q2", players=1)
    ana_four, four = await _match(client, "qms_q4", players=3)
    viewer = await _user(client, "qms_q_viewer@test.com", "Viewer")
    await _make_friends(client, viewer, ana_two)
    await _make_friends(client, viewer, ana_four)

    assert await _statements(client, viewer, four) == await _statements(client, viewer, two)
