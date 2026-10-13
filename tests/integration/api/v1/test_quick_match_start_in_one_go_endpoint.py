"""
Tests de integración de POST /api/v1/quick-matches/start (FE #848).

Crear e iniciar una partida rápida en una sola petición: el asistente ya no
crea nada hasta «Confirmar e iniciar», así que salir a medias no deja una
partida «Pendiente». Tabla aprobada el 13 oct 2026:

    #   caso                                        | respuesta
    ----|---------------------------------------------|---------------------------------
    1   todo bien                                   | 201, en juego, hándicaps fijados
    2   algo falla                                  | ninguna partida guardada
    4   barra que el campo no tiene                 | 422
    5   no es amigo                                 | 403
    6   plantilla incompleta                        | 422
    7   anotadores sin el creador                   | 422
    8   hándicap fuera de rango, invitado sin nombre| 422 (cuerpo)
    8b  invitado con el nombre en blanco            | 422, no un 500
    9   sin sesión                                  | 401
    10  la lista de amigos trae su hándicap          | requester/addressee_handicap
"""

import pytest
from httpx import AsyncClient

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


async def _escenario(client: AsyncClient, sufijo: str, amigos: bool = True):
    admin = await create_admin_user(client, f"qs_admin_{sufijo}@test.com", PASSWORD, "Admin", "Quick")
    creator = await create_authenticated_user(
        client, f"qs_creator_{sufijo}@test.com", PASSWORD, "Creator", "Quick"
    )
    friend = await create_authenticated_user(
        client, f"qs_friend_{sufijo}@test.com", PASSWORD, "Friend", "Quick"
    )
    course = await create_golf_course(client, creator["cookies"])
    await approve_golf_course(client, admin["cookies"], course["id"])
    if amigos:
        await _make_friends(client, creator, friend)
    set_auth_cookies(client, creator["cookies"])
    return creator, friend, course["id"]


def _cuerpo(course_id: str, creator: dict, **extra) -> dict:
    return {
        "golf_course_id": course_id,
        "match_format": "SINGLES",
        "creator_tee_color": "WHITE",
        "creator_tee_gender": "MALE",
        "scorer_user_ids": [creator["user"]["id"]],
        **extra,
    }


def _amigo(friend: dict, **extra) -> dict:
    return {
        "friend_user_id": friend["user"]["id"],
        "tee_color": "YELLOW",
        "tee_gender": "MALE",
        **extra,
    }


async def _mis_partidas(client: AsyncClient) -> list:
    response = await client.get("/api/v1/quick-matches/me")
    assert response.status_code == 200, response.text
    data = response.json()
    return data["quick_matches"] if isinstance(data, dict) else data


class TestStartInOneGo:
    @pytest.mark.asyncio
    async def test_1_creates_and_starts_with_frozen_handicaps(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client, "ok")

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(
                course_id,
                creator,
                creator_handicap=9.5,
                friends=[_amigo(friend, handicap=30.0)],
                scorer_user_ids=[creator["user"]["id"], friend["user"]["id"]],
            ),
        )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert [p["handicap"] for p in data["participants"]] == [9.5, 30.0]
        assert set(data["scorer_ids"]) == {creator["user"]["id"], friend["user"]["id"]}
        assert len(await _mis_partidas(client)) == 1

    @pytest.mark.asyncio
    async def test_1b_guests_without_account(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, "guest", amigos=False)

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(
                course_id,
                creator,
                guests=[
                    {
                        "first_name": "Ana",
                        "last_name": "Pérez",
                        "handicap": 18.4,
                        "tee_color": "YELLOW",
                        "tee_gender": "MALE",
                    }
                ],
            ),
        )

        assert response.status_code == 201, response.text
        assert [p["is_guest"] for p in response.json()["participants"]] == [False, True]


class TestNothingIsSavedOnFailure:
    @pytest.mark.asyncio
    async def test_4_tee_not_on_the_course_returns_422(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client, "tee")

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(
                course_id, creator, friends=[_amigo(friend, tee_color="RED", tee_gender="FEMALE")]
            ),
        )

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_5_not_a_friend_returns_403(self, client: AsyncClient):
        creator, stranger, course_id = await _escenario(client, "stranger", amigos=False)

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(course_id, creator, friends=[_amigo(stranger)]),
        )

        assert response.status_code == 403
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_6_incomplete_roster_returns_422(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, "roster", amigos=False)

        response = await client.post(
            "/api/v1/quick-matches/start", json=_cuerpo(course_id, creator)
        )

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_7_scorers_without_the_creator_return_422(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client, "scorers")

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(
                course_id,
                creator,
                friends=[_amigo(friend)],
                scorer_user_ids=[friend["user"]["id"]],
            ),
        )

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_7b_duplicated_friend_returns_409(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client, "dup")

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(
                course_id,
                creator,
                match_format=None,
                scoring_format="MEDAL",
                friends=[_amigo(friend), _amigo(friend)],
            ),
        )

        assert response.status_code == 409
        assert await _mis_partidas(client) == []


class TestTheBody:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "extra",
        [
            {"creator_handicap": 60},
            {"guests": [{"first_name": "", "last_name": "Pérez"}]},
            {"scorer_user_ids": []},
        ],
    )
    async def test_8_invalid_body_returns_422(self, client: AsyncClient, extra: dict):
        creator, _friend, course_id = await _escenario(
            client, f"body{len(str(extra))}", amigos=False
        )

        response = await client.post(
            "/api/v1/quick-matches/start", json=_cuerpo(course_id, creator, **extra)
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_8b_blank_guest_name_returns_422_not_500(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, "blank", amigos=False)

        response = await client.post(
            "/api/v1/quick-matches/start",
            json=_cuerpo(
                course_id,
                creator,
                guests=[{"first_name": "   ", "last_name": "Pérez"}],
            ),
        )

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_9_requires_authentication(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, "anon", amigos=False)
        client.cookies.clear()

        response = await client.post(
            "/api/v1/quick-matches/start", json=_cuerpo(course_id, creator)
        )

        assert response.status_code == 401


class TestFriendsCarryTheirHandicap:
    @pytest.mark.asyncio
    async def test_10_friends_list_has_both_handicaps(self, client: AsyncClient):
        _creator, _friend, _course_id = await _escenario(client, "friends")

        response = await client.get("/api/v1/friends/me")

        assert response.status_code == 200, response.text
        (item,) = response.json()["friendships"]
        assert "requester_handicap" in item
        assert "addressee_handicap" in item
