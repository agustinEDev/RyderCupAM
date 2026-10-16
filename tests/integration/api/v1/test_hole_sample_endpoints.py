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
| La fila guardada                                | Sin columna de quién la mandó              |
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from tests.conftest import create_authenticated_user, create_golf_course
from tests.integration.api.v1.test_hole_map_endpoints import _as, _in_db, _save_map, _scenario

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = {"latitude": 36.28, "longitude": -5.33}
GREEN = {"latitude": 36.28 + 300 / M_PER_DEGREE, "longitude": -5.33}
CODO = {"latitude": 36.2815, "longitude": -5.331}
BODY = {"tee": SALIDA, "bends": [CODO], "green_center": GREEN}


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
    assert hole_3["collecting"] is True
    assert hole_3["first_sample"]["tee"] == SALIDA
    assert hole_3["first_sample"]["bends"] == [CODO]
    assert hole_3["first_sample"]["green_center"] == pytest.approx(GREEN)


@pytest.mark.asyncio
async def test_e1_the_fourth_is_204_and_not_stored(client: AsyncClient):
    """
    GIVEN: Tres muestras del hoyo 1 (del mismo jugador)
    WHEN: Manda la cuarta
    THEN: 204 igual que las otras; en la BD siguen siendo tres y el hoyo ya no recoge
    """
    course_id, _, _, player = await _scenario(client, "e1b")
    c = _as(client, player)
    for _ in range(3):
        assert (await c.post(_url(course_id), json=BODY)).status_code == 204

    response = await c.post(_url(course_id), json={"tee": SALIDA, "green_center": GREEN})

    assert response.status_code == 204
    assert await _rows(course_id) == 3
    hole_1 = (await c.get(_list(course_id))).json()[0]
    assert hole_1["collecting"] is False
    assert hole_1["first_sample"]["bends"] == [CODO]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"tee": SALIDA, "bends": [CODO, CODO, CODO], "green_center": GREEN},
        {"tee": SALIDA, "green_center": _north(30)},
        {"tee": SALIDA, "green_center": _north(800)},
        {"tee": {"latitude": 91, "longitude": 0}, "green_center": GREEN},
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
        {"green_center": GREEN},
        {"tee": None, "green_center": GREEN},
        {"tee": SALIDA},
        {"tee": [36.28, -5.33], "green_center": GREEN},
        {"tee": SALIDA, "bends": [CODO] * 21, "green_center": GREEN},
        {"tee": {**SALIDA, "altitude": 3}, "green_center": GREEN},
    ],
    ids=["extra", "marked_at", "no-tee", "null-tee", "no-green", "list", "21-bends", "point-extra"],
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
    GIVEN: Dos muestras en el hoyo 1, tres en el 2 y ninguna en el resto
    WHEN: Se leen
    THEN: 18 hoyos en orden; el 1 recoge, el 2 no, el resto vacío y recogiendo;
          cada hoyo trae solo número, primera muestra y si recoge
    """
    course_id, _, _, player = await _scenario(client, "e3")
    c = _as(client, player)
    for _ in range(2):
        await c.post(_url(course_id, 1), json=BODY)
    for _ in range(3):
        await c.post(_url(course_id, 2), json=BODY)

    data = (await c.get(_list(course_id))).json()

    assert [h["hole_number"] for h in data] == list(range(1, 19))
    assert all(set(h) == {"hole_number", "first_sample", "collecting"} for h in data)
    assert set(data[0]["first_sample"]) == {"tee", "bends", "green_center"}
    assert (data[0]["collecting"], data[1]["collecting"]) == (True, False)
    assert all(h["first_sample"] is None and h["collecting"] is True for h in data[2:])
