"""
Integration tests de las muestras anónimas de hoyo (BE #532, 16 oct 2026).

- POST /api/v1/golf-courses/{id}/hole-map/samples/{hole}   mandar una muestra
- GET  /api/v1/golf-courses/{id}/hole-map/samples          estado de los 18 hoyos

| Caso                                            | Resultado                                  |
|-------------------------------------------------|--------------------------------------------|
| Primera muestra con codo                        | 204, y sale como primera del hoyo          |
| Cuarta muestra                                  | 204, y en la BD siguen siendo tres         |
| Tres codos, 30 m, 800 m, latitud 91             | 204, y no se guarda                        |
| A más de 3 km del campo                         | 204, y no se guarda                        |
| Hoyo con mapa aprobado completo                 | 204, y se guarda                           |
| Campo que no existe o pendiente                 | 404 GOLF_COURSE_NOT_FOUND (mandar y leer)  |
| Hoyo 0 o 19                                     | 422 HOLE_NOT_IN_COURSE                     |
| Campo de más, sin salida o sin green, 21 codos  | 422 de validación                          |
| Sin sesión                                      | 401                                        |
| Lectura                                         | 18 hoyos; recoge hasta tres; nada de quién |
| La fila guardada                                | Sin columna de quién la mandó; solo el día |
| Mismo id dos veces                              | 204 las dos, y una fila                    |
| Mismo jugador y hoyo antes de 10 min            | 204, y no se guarda                        |
| Sin id, o un id que no es un UUID               | 422 de validación                          |
| Sin color o género, o con valores que no existen | 422 de validación (el género puede ser null) |
| 3 amarillas-hombre y 3 rojas-mujer, y una 4.ª   | 204 todas; seis filas                      |
| Lectura con varias barras                       | Por orden de su primera muestra            |
| Barra resuelta contra el campo                  | Hombre en amarillas sin género, misma barra; azules que no tiene, no se guardan |
| Sentry en estas rutas                           | Nunca recibe al usuario; en otras, sí      |
"""

from uuid import uuid4

import pytest
import sentry_sdk
from httpx import AsyncClient
from sqlalchemy import text

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from tests.conftest import approve_golf_course, create_authenticated_user, create_golf_course
from tests.integration.api.v1.test_hole_map_endpoints import (
    _as,
    _in_db,
    _make_admin,
    _save_map,
    _scenario,
)

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = {"latitude": 36.28, "longitude": -5.33}
GREEN = {"latitude": 36.28 + 300 / M_PER_DEGREE, "longitude": -5.33}
CODO = {"latitude": 36.2815, "longitude": -5.331}
BODY = {
    "id": "6f0e2b1c-3d4a-4b5c-8d6e-7f8091a2b3c4",
    "tee_color": "YELLOW",
    "tee_gender": "MALE",
    "tee": SALIDA,
    "bends": [CODO],
    "green_center": GREEN,
}


def _new(body: dict = BODY) -> dict:
    """La misma muestra con un id nuevo, como la genera el móvil en cada envío."""
    return {**body, "id": str(uuid4())}


async def _players(client: AsyncClient, tag: str, n: int) -> list[dict]:
    """Jugadores distintos: cada uno aporta una muestra por hoyo cada 10 minutos."""
    return [
        await create_authenticated_user(
            client, f"p{i}-{tag}@test.com", "P@ssw0rd123!", "Player", "Map"
        )
        for i in range(n)
    ]


def _url(course_id: str, hole: int | str = 1) -> str:
    return f"/api/v1/golf-courses/{course_id}/hole-map/samples/{hole}"


def _list(course_id: str) -> str:
    return f"/api/v1/golf-courses/{course_id}/hole-map/samples"


def _north(metres: float) -> dict:
    return {"latitude": SALIDA["latitude"] + metres / M_PER_DEGREE, "longitude": -5.33}


async def _rows(course_id: str, hole: int = 1) -> int:
    async def work(session):
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM golf_course_hole_samples "
                    "WHERE golf_course_id = :id AND hole_number = :hole"
                ),
                {"id": course_id, "hole": hole},
            )
        ).scalar_one()

    return await _in_db(work)


# ============================================================================
# E1 — Mandar muestras
# ============================================================================


@pytest.mark.asyncio
async def test_e1_first_sample_is_204_and_read_back(client: AsyncClient):
    """
    GIVEN: Un campo aprobado sin muestras
    WHEN: Un jugador manda una muestra del hoyo 3 con un codo y se leen
    THEN: 204 sin cuerpo; el hoyo 3 la trae como primera (puntos con nombre) y sigue recogiendo
    """
    course_id, _, _, player = await _scenario(client, "e1")
    c = _as(client, player)

    response = await c.post(_url(course_id, 3), json=BODY)

    assert response.status_code == 204
    assert response.content == b""
    read = await c.get(_list(course_id))
    assert read.status_code == 200
    hole_3 = read.json()[2]
    assert hole_3["hole_number"] == 3
    (tee,) = hole_3["tees"]
    assert (tee["tee_color"], tee["tee_gender"]) == ("YELLOW", "MALE")
    assert tee["collecting"] is True
    assert tee["first_sample"]["tee"] == SALIDA
    assert tee["first_sample"]["bends"] == [CODO]
    assert tee["first_sample"]["green_center"] == pytest.approx(GREEN)


@pytest.mark.asyncio
async def test_e1_the_fourth_is_204_and_not_stored(client: AsyncClient):
    """
    GIVEN: Tres muestras del hoyo 1, de tres jugadores
    WHEN: Un cuarto manda la suya
    THEN: 204 igual que las otras; en la BD siguen siendo tres y el hoyo ya no recoge
    """
    course_id, _, _, player = await _scenario(client, "e1b")
    for other in await _players(client, "e1b", 3):
        assert (await _as(client, other).post(_url(course_id), json=_new())).status_code == 204
    c = _as(client, player)

    response = await c.post(_url(course_id), json=_new({**BODY, "bends": []}))

    assert response.status_code == 204
    assert await _rows(course_id) == 3
    (tee,) = (await c.get(_list(course_id))).json()[0]["tees"]
    assert tee["collecting"] is False
    assert tee["first_sample"]["bends"] == [CODO]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "bends": [CODO, CODO, CODO]},
        {**BODY, "bends": [], "green_center": _north(30)},
        {**BODY, "bends": [], "green_center": _north(800)},
        {**BODY, "tee": {"latitude": 91, "longitude": 0}},
    ],
    ids=["three-bends", "30m", "800m", "lat-91"],
)
async def test_e1_impossible_samples_are_204_and_not_stored(client: AsyncClient, body):
    """
    GIVEN: Tres codos, un green a 30 m o a 800 m, o una latitud de 91
    WHEN: Se manda la muestra
    THEN: 204 (el jugador no nota nada) y no se guarda
    """
    course_id, _, _, player = await _scenario(client, f"e1c{len(str(body))}")

    response = await _as(client, player).post(_url(course_id), json=body)

    assert response.status_code == 204
    assert await _rows(course_id) == 0


@pytest.mark.asyncio
async def test_e1_far_from_the_course_is_204_and_not_stored(client: AsyncClient):
    """
    GIVEN: Un campo con ubicación a ~5,5 km de la muestra
    WHEN: Se manda
    THEN: 204, y no se guarda
    """
    course_id, _, _, player = await _scenario(client, "e1d")

    async def place(session):
        await session.execute(
            text("UPDATE golf_courses SET latitude = 36.33, longitude = -5.33 WHERE id = :id"),
            {"id": course_id},
        )

    await _in_db(place)

    response = await _as(client, player).post(_url(course_id), json=BODY)

    assert response.status_code == 204
    assert await _rows(course_id) == 0


@pytest.mark.asyncio
async def test_e1_a_hole_with_a_full_approved_map_takes_samples(client: AsyncClient):
    """
    GIVEN: Un mapa aprobado con el hoyo 1 completo (salida y green de OSM)
    WHEN: Se manda una muestra del hoyo 1
    THEN: 204, y se guarda (ya no hay HOLE_ALREADY_MAPPED)
    """
    course_id, _, admin_email, player = await _scenario(client, "e1e")
    await _save_map(course_id, approved_by_email=admin_email)

    response = await _as(client, player).post(_url(course_id), json=BODY)

    assert response.status_code == 204
    assert await _rows(course_id) == 1


@pytest.mark.asyncio
async def test_e1_the_row_does_not_know_who_sent_it(client: AsyncClient):
    """
    GIVEN: La tabla de muestras
    WHEN: Se miran sus columnas
    THEN: Ninguna dice quién la mandó
    """
    await _scenario(client, "e1f")

    async def columns(session):
        result = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'golf_course_hole_samples'"
            )
        )
        return {row[0] for row in result}

    names = await _in_db(columns)

    assert "golf_course_id" in names
    assert not any("user" in name or "author" in name for name in names)


# ============================================================================
# E2 — Errores
# ============================================================================


@pytest.mark.asyncio
async def test_e2_unknown_course_is_404(client: AsyncClient):
    """
    GIVEN: Un id que no es de ningún campo
    WHEN: Se manda una muestra o se leen
    THEN: 404 GOLF_COURSE_NOT_FOUND en los dos, con su mensaje fijo
    """
    _, _, _, player = await _scenario(client, "e2a")
    nadie = str(GolfCourseId.generate())
    c = _as(client, player)

    for response in (await c.post(_url(nadie), json=BODY), await c.get(_list(nadie))):
        assert response.status_code == 404
        assert response.json() == {
            "detail": "Golf course not found",
            "error_code": "GOLF_COURSE_NOT_FOUND",
        }


@pytest.mark.asyncio
async def test_e2_courses_players_cannot_see_are_404(client: AsyncClient):
    """
    GIVEN: Un campo pendiente de aprobar
    WHEN: Un jugador manda una muestra o las lee
    THEN: 404 GOLF_COURSE_NOT_FOUND, y no se guarda nada
    """
    creator = await create_authenticated_user(
        client, "creator-e2b@test.com", "P@ssw0rd123!", "Creator", "Map"
    )
    course = await create_golf_course(client, creator["cookies"])
    player = await create_authenticated_user(
        client, "player-e2b@test.com", "P@ssw0rd123!", "Player", "Map"
    )
    c = _as(client, player)

    for response in (await c.post(_url(course["id"]), json=BODY), await c.get(_list(course["id"]))):
        assert response.status_code == 404
        assert response.json()["error_code"] == "GOLF_COURSE_NOT_FOUND"
    assert await _rows(course["id"]) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("hole", [0, 19])
async def test_e2_hole_not_in_course_is_422(client: AsyncClient, hole):
    """
    GIVEN: Un campo aprobado
    WHEN: Se manda una muestra del hoyo 0 o del 19
    THEN: 422 HOLE_NOT_IN_COURSE, con su mensaje fijo
    """
    course_id, _, _, player = await _scenario(client, f"e2c{hole}")

    response = await _as(client, player).post(_url(course_id, hole), json=BODY)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "This course has no such hole",
        "error_code": "HOLE_NOT_IN_COURSE",
    }


@pytest.mark.asyncio
async def test_e2_hole_ten_is_fine(client: AsyncClient):
    """
    GIVEN: Un campo aprobado
    WHEN: Se manda una muestra del hoyo 10
    THEN: 204, y se guarda
    """
    course_id, _, _, player = await _scenario(client, "e2d")

    response = await _as(client, player).post(_url(course_id, 10), json=BODY)

    assert response.status_code == 204
    assert await _rows(course_id, 10) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "outline": []},
        {**BODY, "marked_at": "2026-10-15T10:00:00+02:00"},
        {"id": BODY["id"], "green_center": GREEN},
        {**BODY, "tee": None},
        {"id": BODY["id"], "tee": SALIDA},
        {**BODY, "tee": [36.28, -5.33]},
        {**BODY, "bends": [CODO] * 21},
        {**BODY, "tee": {**SALIDA, "altitude": 3}},
        {k: v for k, v in BODY.items() if k != "id"},
        {**BODY, "id": None},
        {**BODY, "id": "no-es-un-uuid"},
        {**BODY, "id": 7},
        {k: v for k, v in BODY.items() if k != "tee_color"},
        {**BODY, "tee_color": "PURPLE"},
        {**BODY, "tee_color": None},
        {**BODY, "tee_color": "yellow"},
        {k: v for k, v in BODY.items() if k != "tee_gender"},
        {**BODY, "tee_gender": "OTHER"},
        {**BODY, "tee_gender": "male"},
    ],
    ids=[
        "extra",
        "marked_at",
        "no-tee",
        "null-tee",
        "no-green",
        "list",
        "21-bends",
        "point-extra",
        "no-id",
        "null-id",
        "text-id",
        "number-id",
        "no-color",
        "purple",
        "null-color",
        "lowercase-color",
        "no-gender",
        "other-gender",
        "lowercase-gender",
    ],
)
async def test_e2_malformed_bodies_are_422(client: AsyncClient, body):
    """
    GIVEN: Un campo de más (también el `marked_at` de las marcas), sin salida, salida
           nula, sin green, un punto como lista, 21 codos o un punto con un campo de más
    WHEN: Se manda la muestra
    THEN: 422 de validación, y no se guarda
    """
    course_id, _, _, player = await _scenario(client, f"e2e{len(str(body))}")

    response = await _as(client, player).post(_url(course_id), json=body)

    assert response.status_code == 422
    assert await _rows(course_id) == 0


@pytest.mark.asyncio
async def test_e2_needs_a_session_and_valid_ids(client: AsyncClient):
    """
    GIVEN: Sin sesión, o con un id de campo o un hoyo que no son válidos
    WHEN: Se manda una muestra o se leen
    THEN: 401, y 422
    """
    course_id, _, _, player = await _scenario(client, "e2f")

    client.cookies.clear()
    assert (await client.post(_url(course_id), json=BODY)).status_code == 401
    assert (await client.get(_list(course_id))).status_code == 401
    c = _as(client, player)
    assert (await c.post(_url("no-es-un-id"), json=BODY)).status_code == 422
    assert (await c.post(_url(course_id, "uno"), json=BODY)).status_code == 422
    assert (await c.get(_list("no-es-un-id"))).status_code == 422


@pytest.mark.asyncio
async def test_e2_the_old_marks_endpoints_are_gone(client: AsyncClient):
    """
    GIVEN: Las marcas por jugador, retiradas
    WHEN: Se llama a sus endpoints
    THEN: Ya no existen (404 o 405 de rutas, sin error_code)
    """
    course_id, _, _, player = await _scenario(client, "e2g")
    c = _as(client, player)

    put = await c.put(f"/api/v1/golf-courses/{course_id}/hole-map/marks/1", json=BODY)
    mine = await c.get(f"/api/v1/golf-courses/{course_id}/hole-map/marks/mine")

    assert put.status_code in (404, 405)
    assert mine.status_code in (404, 405)
    assert "error_code" not in put.json()
    assert "error_code" not in mine.json()


# ============================================================================
# E3 — La lectura
# ============================================================================


@pytest.mark.asyncio
async def test_e3_eighteen_holes_and_nothing_about_who_or_how_many(client: AsyncClient):
    """
    GIVEN: Dos muestras en el hoyo 1, tres en el 2 (amarillas de hombre) y ninguna en el resto
    WHEN: Se leen
    THEN: 18 hoyos en orden; las amarillas del 1 recogen, las del 2 no, el resto sin
          barras; cada barra trae solo color, género, primera muestra y si recoge
    """
    course_id, _, _, player = await _scenario(client, "e3")
    a, b, c3 = await _players(client, "e3", 3)
    for who, holes in ((a, (1, 2)), (b, (1, 2)), (c3, (2,))):
        for hole in holes:
            await _as(client, who).post(_url(course_id, hole), json=_new())
    c = _as(client, player)

    data = (await c.get(_list(course_id))).json()

    assert [h["hole_number"] for h in data] == list(range(1, 19))
    assert all(set(h) == {"hole_number", "tees"} for h in data)
    (uno,), (dos,) = data[0]["tees"], data[1]["tees"]
    assert set(uno) == {"tee_color", "tee_gender", "first_sample", "collecting"}
    assert set(uno["first_sample"]) == {"tee", "bends", "green_center"}
    assert (uno["collecting"], dos["collecting"]) == (True, False)
    assert all(h["tees"] == [] for h in data[2:])


# ============================================================================
# E4 — Revisión del 16 oct: id del móvil, ventana por jugador y Sentry
# ============================================================================


@pytest.mark.asyncio
async def test_e4_the_same_id_twice_is_stored_once(client: AsyncClient):
    """
    GIVEN: Una muestra mandada (el móvil no recibió la respuesta)
    WHEN: La reenvía con el mismo id, y otro jugador manda también ese id
    THEN: 204 las tres veces, y hay una sola fila
    """
    course_id, _, _, player = await _scenario(client, "e4a")
    (other,) = await _players(client, "e4a", 1)

    first = await _as(client, player).post(_url(course_id), json=BODY)
    again = await _as(client, player).post(_url(course_id), json=BODY)
    from_other = await _as(client, other).post(_url(course_id), json=BODY)

    assert [r.status_code for r in (first, again, from_other)] == [204, 204, 204]
    assert await _rows(course_id) == 1


@pytest.mark.asyncio
async def test_e4_the_same_player_within_ten_minutes_is_not_stored(client: AsyncClient):
    """
    GIVEN: Una muestra del jugador en el hoyo 1
    WHEN: Manda otra distinta (otro id) del hoyo 1 en seguida, y una del hoyo 2
    THEN: 204 todas; del hoyo 1 hay una, y la del hoyo 2 se guarda
    """
    course_id, _, _, player = await _scenario(client, "e4b")
    c = _as(client, player)
    await c.post(_url(course_id), json=_new())

    second = await c.post(_url(course_id), json=_new())
    other_hole = await c.post(_url(course_id, 2), json=_new())

    assert (second.status_code, other_hole.status_code) == (204, 204)
    assert await _rows(course_id, 1) == 1
    assert await _rows(course_id, 2) == 1


@pytest.mark.asyncio
async def test_e4_only_the_day_is_stored(client: AsyncClient):
    """
    GIVEN: Una muestra guardada
    WHEN: Se mira la fila
    THEN: Lleva el día (DATE) y un orden de llegada, pero ninguna hora
    """
    course_id, _, _, player = await _scenario(client, "e4c")
    await _as(client, player).post(_url(course_id), json=_new())

    async def columns(session):
        result = await session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'golf_course_hole_samples'"
            )
        )
        return dict(result.all())

    types = await _in_db(columns)

    assert types["received_on"] == "date"
    assert types["seq"] == "bigint"
    assert not any("timestamp" in kind or "time" in name for name, kind in types.items())


@pytest.mark.asyncio
async def test_e4_sentry_never_gets_the_user_on_these_routes(client: AsyncClient, monkeypatch):
    """
    GIVEN: Un jugador con sesión
    WHEN: Manda una muestra, las lee y, para comparar, pide el mapa del campo
    THEN: En las rutas de muestras Sentry no recibe usuario; en la del mapa, sí
    """
    course_id, _, _, player = await _scenario(client, "e4d")
    calls: list = []
    monkeypatch.setattr(sentry_sdk, "set_user", calls.append)
    c = _as(client, player)

    assert (await c.post(_url(course_id), json=_new())).status_code == 204
    assert (await c.get(_list(course_id))).status_code == 200
    assert (await c.get(f"{_list(course_id)}/")).status_code in (200, 307, 404)

    assert calls
    assert all(user is None for user in calls)
    await c.get(f"/api/v1/golf-courses/{course_id}/hole-map")
    assert any(isinstance(user, dict) and user.get("id") for user in calls)


# ============================================================================
# E5 — Por barra
# ============================================================================


def _tee(color: str, gender: str | None, rating: float) -> dict:
    return {
        "identifier": f"{color}-{gender}",
        "color": color,
        "tee_gender": gender,
        "course_rating": rating,
        "slope_rating": 128,
        "par": 72,
    }


async def _scenario_with_tees(client: AsyncClient, tag: str, tees: list[dict]):
    """Como `_scenario`, pero con las barras que se pidan."""
    creator = await create_authenticated_user(
        client, f"creator-{tag}@test.com", "P@ssw0rd123!", "Creator", "Map"
    )
    course = await create_golf_course(
        client,
        creator["cookies"],
        {
            "name": f"Campo {tag}",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": tees,
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        },
    )
    admin_email = f"admin-{tag}@test.com"
    admin = await create_authenticated_user(client, admin_email, "AdminPass123!", "Admin", "Map")
    await _make_admin(admin_email)
    await approve_golf_course(client, admin["cookies"], course["id"])
    player = await create_authenticated_user(
        client, f"player-{tag}@test.com", "P@ssw0rd123!", "Player", "Map"
    )
    return course["id"], player


@pytest.mark.asyncio
async def test_e5_the_cap_is_per_tee_and_the_read_lists_each_tee(client: AsyncClient):
    """
    GIVEN: Un campo con rojas de mujer, amarillas de hombre y blancas sin género; tres
           jugadores mandan el hoyo 1 desde rojas y desde amarillas (las rojas primero),
           y otro desde blancas
    WHEN: Ese otro manda además una desde amarillas, y se leen
    THEN: 204 todas; 3 + 3 + 1 filas; el hoyo 1 trae tres barras en el orden de su
          primera muestra: rojas y amarillas llenas, blancas recogiendo
    """
    course_id, player = await _scenario_with_tees(
        client,
        "e5",
        [_tee("RED", "FEMALE", 70.0), _tee("YELLOW", "MALE", 71.0), _tee("WHITE", None, 72.0)],
    )
    rojas = {"tee_color": "RED", "tee_gender": "FEMALE"}
    for who in await _players(client, "e5", 3):
        c = _as(client, who)
        assert (await c.post(_url(course_id), json=_new({**BODY, **rojas}))).status_code == 204
        assert (await c.post(_url(course_id), json=_new())).status_code == 204
    c = _as(client, player)
    blancas = await c.post(
        _url(course_id), json=_new({**BODY, "tee_color": "WHITE", "tee_gender": None})
    )

    cuarta = await c.post(_url(course_id), json=_new())

    assert (blancas.status_code, cuarta.status_code) == (204, 204)
    assert await _rows(course_id) == 7
    tees = (await c.get(_list(course_id))).json()[0]["tees"]
    assert [(t["tee_color"], t["tee_gender"], t["collecting"]) for t in tees] == [
        ("RED", "FEMALE", False),
        ("YELLOW", "MALE", False),
        ("WHITE", None, True),
    ]


@pytest.mark.asyncio
async def test_e5_the_tee_is_resolved_against_the_course(client: AsyncClient):
    """
    GIVEN: Un campo con amarillas sin género (y rojas de mujer)
    WHEN: Un jugador manda desde amarillas de hombre, otro desde amarillas sin género, y
          un tercero desde azules (el campo no las tiene)
    THEN: 204 las tres; las dos amarillas van a la misma barra, sin género; las azules no se guardan
    """
    course_id, player = await _scenario_with_tees(
        client, "e5b", [_tee("YELLOW", None, 71.0), _tee("RED", "FEMALE", 70.0)]
    )
    a, b = await _players(client, "e5b", 2)

    responses = [
        await _as(client, a).post(_url(course_id), json=_new()),
        await _as(client, b).post(_url(course_id), json=_new({**BODY, "tee_gender": None})),
        await _as(client, player).post(_url(course_id), json=_new({**BODY, "tee_color": "BLUE"})),
    ]

    assert [r.status_code for r in responses] == [204, 204, 204]
    assert await _rows(course_id) == 2
    (tee,) = (await _as(client, player).get(_list(course_id))).json()[0]["tees"]
    assert (tee["tee_color"], tee["tee_gender"]) == ("YELLOW", None)
