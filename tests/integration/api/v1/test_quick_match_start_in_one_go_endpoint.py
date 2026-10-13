"""
Tests de integración de POST /api/v1/quick-matches/start (FE #848).

Crear e iniciar una partida rápida en una sola petición: el asistente ya no
crea nada hasta «Confirmar e iniciar», así que salir a medias no deja una
partida «Pendiente». Tabla aprobada el 13 oct 2026 (y su revisión):

    #   caso                                        | respuesta
    ----|---------------------------------------------|---------------------------------
    1   todo bien                                   | 201, en juego; releída, guardada
        |                                             | con anotadores y hándicaps fijos
    1b  invitados sin cuenta, en su orden           | 201, el orden de la lista
    1c  parejas con equipos                         | 201, equipos A/A/B/B
    1d  el perfil cambia después de empezar         | lo fijado no se mueve
    2   algo falla                                  | ninguna partida guardada
    4   barra que el campo no tiene (amigo,         | 422
        | invitado) o campo sin aprobar               |
    5   amigo inexistente / no amigo / repetido     | 404 / 403 / 409
    6   plantilla incompleta                        | 422
    7   anotadores sin el creador o repetidos       | 422
    8   cuerpo inválido (rango, nombre vacío, sin   | 422
        | id)                                         |
    8b  invitado con el nombre en blanco            | 422, no un 500
    9   sin sesión                                  | 401
    10  la lista de amigos trae su hándicap         | con su valor, o nulo; las
        |                                             | solicitudes, sin el campo
    11  el mismo id otra vez                        | 200 con la que hay; de otro, 409
"""

from uuid import uuid4

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


async def _escenario(client: AsyncClient, amigos: bool = True, aprobado: bool = True):
    # Un sufijo al azar por escenario: nada de colisiones de emails entre casos
    sufijo = uuid4().hex[:8]
    admin = await create_admin_user(
        client, f"qs_admin_{sufijo}@test.com", PASSWORD, "Admin", "Quick"
    )
    creator = await create_authenticated_user(
        client, f"qs_creator_{sufijo}@test.com", PASSWORD, "Creator", "Quick"
    )
    friend = await create_authenticated_user(
        client, f"qs_friend_{sufijo}@test.com", PASSWORD, "Friend", "Quick"
    )
    course = await create_golf_course(client, creator["cookies"])
    if aprobado:
        await approve_golf_course(client, admin["cookies"], course["id"])
    if amigos:
        await _make_friends(client, creator, friend)
    set_auth_cookies(client, creator["cookies"])
    return creator, friend, course["id"]


async def _pon_handicap(client: AsyncClient, user: dict, handicap: float) -> None:
    client.cookies.clear()
    response = await client.post(
        "/api/v1/handicaps/update-manual",
        json={"user_id": user["user"]["id"], "handicap": handicap},
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert response.status_code == 200, response.text


def _cuerpo(course_id: str, creator: dict, **extra) -> dict:
    return {
        "quick_match_id": str(uuid4()),
        "golf_course_id": course_id,
        "match_format": "SINGLES",
        "creator_tee_color": "WHITE",
        "creator_tee_gender": "MALE",
        "scorer_user_ids": [creator["user"]["id"]],
        "participants": [],
        **extra,
    }


def _amigo(friend: dict, **extra) -> dict:
    return {
        "kind": "FRIEND",
        "friend_user_id": friend["user"]["id"],
        "tee_color": "YELLOW",
        "tee_gender": "MALE",
        **extra,
    }


def _invitado(**extra) -> dict:
    return {
        "kind": "GUEST",
        "first_name": "Ana",
        "last_name": "Pérez",
        "handicap": 18.4,
        "tee_color": "YELLOW",
        "tee_gender": "MALE",
        **extra,
    }


async def _mis_partidas(client: AsyncClient) -> list:
    response = await client.get("/api/v1/quick-matches/me")
    assert response.status_code == 200, response.text
    return response.json()["quick_matches"]


async def _inicia(client: AsyncClient, cuerpo: dict):
    return await client.post("/api/v1/quick-matches/start", json=cuerpo)


class TestStartInOneGo:
    @pytest.mark.asyncio
    async def test_1_creates_starts_and_persists_frozen_handicaps(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)

        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                creator,
                creator_handicap=9.5,
                participants=[_amigo(friend, handicap=30.0)],
                scorer_user_ids=[creator["user"]["id"], friend["user"]["id"]],
            ),
        )

        assert response.status_code == 201, response.text
        detail = await client.get(f"/api/v1/quick-matches/{response.json()['id']}")
        assert detail.status_code == 200, detail.text
        data = detail.json()
        assert data["status"] == "IN_PROGRESS"
        assert [p["handicap"] for p in data["participants"]] == [9.5, 30.0]
        assert set(data["scorer_ids"]) == {creator["user"]["id"], friend["user"]["id"]}
        assert len(await _mis_partidas(client)) == 1

    @pytest.mark.asyncio
    async def test_1b_guests_without_account_keep_their_order(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)

        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                creator,
                match_format=None,
                scoring_format="MEDAL",
                participants=[_invitado(), _amigo(friend)],
            ),
        )

        assert response.status_code == 201, response.text
        participants = response.json()["participants"]
        assert [p["is_guest"] for p in participants] == [False, True, False]
        assert participants[2]["user_id"] == friend["user"]["id"]

    @pytest.mark.asyncio
    async def test_1c_pairs_with_teams(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)

        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                creator,
                match_format="FOURBALL",
                participants=[
                    _amigo(friend, team="A"),
                    _invitado(team="B"),
                    _invitado(first_name="Bea", team="B"),
                ],
            ),
        )

        assert response.status_code == 201, response.text
        assert [p["team"] for p in response.json()["participants"]] == ["A", "A", "B", "B"]

    @pytest.mark.asyncio
    async def test_1d_a_later_profile_change_does_not_move_the_frozen_handicap(
        self, client: AsyncClient
    ):
        creator, friend, course_id = await _escenario(client)
        await _pon_handicap(client, friend, 20.0)
        set_auth_cookies(client, creator["cookies"])
        response = await _inicia(client, _cuerpo(course_id, creator, participants=[_amigo(friend)]))
        assert response.status_code == 201, response.text

        await _pon_handicap(client, friend, 5.0)
        set_auth_cookies(client, creator["cookies"])
        detail = await client.get(f"/api/v1/quick-matches/{response.json()['id']}")

        assert detail.json()["participants"][1]["handicap"] == 20.0


class TestNothingIsSavedOnFailure:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("quien", ["amigo", "invitado"])
    async def test_4_tee_not_on_the_course_returns_422(self, client: AsyncClient, quien: str):
        creator, friend, course_id = await _escenario(client)
        mala = {"tee_color": "RED", "tee_gender": "FEMALE"}
        jugador = _amigo(friend, **mala) if quien == "amigo" else _invitado(**mala)

        response = await _inicia(client, _cuerpo(course_id, creator, participants=[jugador]))

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_4b_unapproved_course_returns_422(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client, aprobado=False)

        response = await _inicia(client, _cuerpo(course_id, creator, participants=[_amigo(friend)]))

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_5_unknown_friend_returns_404(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, amigos=False)
        fantasma = {"kind": "FRIEND", "friend_user_id": str(uuid4())}

        response = await _inicia(client, _cuerpo(course_id, creator, participants=[fantasma]))

        assert response.status_code == 404
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_5b_not_a_friend_returns_403(self, client: AsyncClient):
        creator, stranger, course_id = await _escenario(client, amigos=False)

        response = await _inicia(
            client, _cuerpo(course_id, creator, participants=[_amigo(stranger)])
        )

        assert response.status_code == 403
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_5c_duplicated_friend_returns_409(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)

        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                creator,
                match_format=None,
                scoring_format="MEDAL",
                participants=[_amigo(friend), _amigo(friend)],
            ),
        )

        assert response.status_code == 409
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_6_incomplete_roster_returns_422(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, amigos=False)

        response = await _inicia(client, _cuerpo(course_id, creator))

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_7_scorers_without_the_creator_return_422(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)

        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                creator,
                participants=[_amigo(friend)],
                scorer_user_ids=[friend["user"]["id"]],
            ),
        )

        assert response.status_code == 422
        assert await _mis_partidas(client) == []


class TestTheBody:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "extra",
        [
            {"creator_handicap": 60},
            {"participants": [{"kind": "GUEST", "first_name": "", "last_name": "Pérez"}]},
            {"participants": [{"kind": "FRIEND", "friend_user_id": str(uuid4()), "handicap": 60}]},
            {"scorer_user_ids": []},
            {"quick_match_id": None},
        ],
    )
    async def test_8_invalid_body_returns_422(self, client: AsyncClient, extra: dict):
        creator, _friend, course_id = await _escenario(client, amigos=False)

        response = await _inicia(client, _cuerpo(course_id, creator, **extra))

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_8_repeated_scorers_return_422(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, amigos=False)
        yo = creator["user"]["id"]

        response = await _inicia(client, _cuerpo(course_id, creator, scorer_user_ids=[yo, yo]))

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_8b_blank_guest_name_returns_422_not_500(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, amigos=False)

        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                creator,
                participants=[{"kind": "GUEST", "first_name": "   ", "last_name": "Pérez"}],
            ),
        )

        assert response.status_code == 422
        assert await _mis_partidas(client) == []

    @pytest.mark.asyncio
    async def test_9_requires_authentication(self, client: AsyncClient):
        creator, _friend, course_id = await _escenario(client, amigos=False)
        client.cookies.clear()

        response = await _inicia(client, _cuerpo(course_id, creator))

        assert response.status_code == 401


class TestRetryIsSafe:
    @pytest.mark.asyncio
    async def test_11_same_id_again_returns_the_existing_match(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)
        cuerpo = _cuerpo(course_id, creator, participants=[_amigo(friend)])

        primera = await _inicia(client, cuerpo)
        segunda = await _inicia(client, cuerpo)

        assert primera.status_code == 201, primera.text
        assert segunda.status_code == 200, segunda.text
        assert segunda.json()["id"] == primera.json()["id"] == cuerpo["quick_match_id"]
        assert len(await _mis_partidas(client)) == 1

    @pytest.mark.asyncio
    async def test_11b_someone_elses_id_returns_409(self, client: AsyncClient):
        creator, friend, course_id = await _escenario(client)
        cuerpo = _cuerpo(course_id, creator, participants=[_amigo(friend)])
        assert (await _inicia(client, cuerpo)).status_code == 201

        set_auth_cookies(client, friend["cookies"])
        response = await _inicia(
            client,
            _cuerpo(
                course_id,
                friend,
                match_format=None,
                scoring_format="MEDAL",
                quick_match_id=cuerpo["quick_match_id"],
            ),
        )

        assert response.status_code == 409


class TestFriendsCarryTheirHandicap:
    @pytest.mark.asyncio
    async def test_10_friends_list_has_each_handicap_or_null(self, client: AsyncClient):
        creator, friend, _course_id = await _escenario(client)
        await _pon_handicap(client, creator, 12.4)
        set_auth_cookies(client, creator["cookies"])

        response = await client.get("/api/v1/friends/me")

        assert response.status_code == 200, response.text
        (item,) = response.json()["friendships"]
        assert item["requester_handicap"] == 12.4
        assert item["addressee_handicap"] is None
        assert item["addressee_id"] == friend["user"]["id"]

    @pytest.mark.asyncio
    async def test_10b_friend_requests_do_not_carry_handicaps(self, client: AsyncClient):
        _creator, friend, _course_id = await _escenario(client, amigos=False)
        sent = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": friend["user"]["id"]}
        )

        assert sent.status_code == 201, sent.text
        assert "requester_handicap" not in sent.json()


class TestTheStepByStepGuestTwin:
    @pytest.mark.asyncio
    async def test_blank_guest_name_on_the_old_endpoint_returns_422_not_500(
        self, client: AsyncClient
    ):
        _creator, _friend, course_id = await _escenario(client, amigos=False)
        created = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": course_id, "match_format": "SINGLES"},
        )
        assert created.status_code == 201, created.text

        response = await client.post(
            f"/api/v1/quick-matches/{created.json()['id']}/participants/guest",
            json={"first_name": "   ", "last_name": "Pérez"},
        )

        assert response.status_code == 422
