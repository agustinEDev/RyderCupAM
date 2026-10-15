"""
Integration tests de las marcas de hoyo de los jugadores (BE #532, PR C).

- PUT /api/v1/golf-courses/{id}/hole-map/marks/{hole}   marcar (o volver a marcar)
- GET /api/v1/golf-courses/{id}/hole-map/marks/mine     mis marcas en el campo

Los errores llevan un código fijo (`error_code`) del que se fía el front.
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
# El hoyo 2 del mapa de prueba tiene salida en (36.291, -5.332) y no tiene green
GREEN_DEL_2 = {"latitude": 36.291 + 300 / M_PER_DEGREE, "longitude": -5.332}


def _url(course_id: str, hole: int | str = 1) -> str:
    return f"/api/v1/golf-courses/{course_id}/hole-map/marks/{hole}"


def _mine(course_id: str) -> str:
    return f"/api/v1/golf-courses/{course_id}/hole-map/marks/mine"


async def _place_course(course_id: str, latitude: float, longitude: float) -> None:
    async def work(session):
        await session.execute(
            text("UPDATE golf_courses SET latitude = :lat, longitude = :lon WHERE id = :id"),
            {"lat": latitude, "lon": longitude, "id": course_id},
        )

    await _in_db(work)


# ============================================================================
# M1 — Marcar y ver las mías
# ============================================================================


@pytest.mark.asyncio
async def test_m1_player_marks_a_hole_and_gets_it_back(client: AsyncClient):
    """
    GIVEN: Un campo sin mapa
    WHEN: Un jugador marca el hoyo 3 (salida, codo, green) y pide las suyas
    THEN: 200 con la marca (puntos con nombre y fecha en UTC con «Z»), y sale en las suyas
    """
    course_id, _, _, player = await _scenario(client, "m1")
    c = _as(client, player)

    response = await c.put(
        _url(course_id, 3), json={"tee": SALIDA, "bends": [CODO], "green_center": GREEN}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["hole_number"] == 3
    assert data["tee"] == SALIDA
    assert data["bends"] == [CODO]
    assert data["green_center"] == pytest.approx(GREEN)
    assert data["marked_at"].endswith("Z")
    mine = await c.get(_mine(course_id))
    assert mine.status_code == 200
    assert mine.json() == [data]


@pytest.mark.asyncio
async def test_m1_marking_again_replaces_it_and_others_do_not_see_it(client: AsyncClient):
    """
    GIVEN: Un jugador que marcó el hoyo 1
    WHEN: Lo vuelve a marcar sin codos, y otro jugador pide las suyas
    THEN: Queda una sola marca (la nueva); el otro no ve ninguna
    """
    course_id, _, _, player = await _scenario(client, "m1b")
    await _as(client, player).put(
        _url(course_id), json={"tee": SALIDA, "bends": [CODO], "green_center": GREEN}
    )

    await _as(client, player).put(_url(course_id), json={"tee": SALIDA, "green_center": GREEN})

    (mark,) = (await _as(client, player).get(_mine(course_id))).json()
    assert mark["bends"] == []
    other = await create_authenticated_user(
        client, "other-m1b@test.com", "P@ssw0rd123!", "Other", "Map"
    )
    assert (await _as(client, other).get(_mine(course_id))).json() == []


# ============================================================================
# M2 — Según lo que tenga el hoyo en el mapa aprobado
# ============================================================================


@pytest.mark.asyncio
async def test_m2_hole_already_mapped_is_409(client: AsyncClient):
    """
    GIVEN: Un mapa aprobado con el hoyo 1 completo
    WHEN: Un jugador lo marca
    THEN: 409 HOLE_ALREADY_MAPPED
    """
    course_id, _, admin_email, player = await _scenario(client, "m2a")
    await _save_map(course_id, approved_by_email=admin_email)

    response = await _as(client, player).put(
        _url(course_id), json={"tee": SALIDA, "green_center": GREEN}
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "HOLE_ALREADY_MAPPED"


@pytest.mark.asyncio
async def test_m2_hole_with_tee_keeps_only_the_green(client: AsyncClient):
    """
    GIVEN: Un mapa aprobado con el hoyo 2 con salida y sin green
    WHEN: Llega una marca con salida, codo y green (hecha sin cobertura antes de aprobarse)
    THEN: 200 con `tee` a null y sin codos: cuenta solo su green
    """
    course_id, _, admin_email, player = await _scenario(client, "m2b")
    await _save_map(course_id, approved_by_email=admin_email)

    response = await _as(client, player).put(
        _url(course_id, 2), json={"tee": SALIDA, "bends": [CODO], "green_center": GREEN_DEL_2}
    )

    assert response.status_code == 200
    data = response.json()
    assert (data["tee"], data["bends"]) == (None, [])
    assert data["green_center"] == pytest.approx(GREEN_DEL_2)


@pytest.mark.asyncio
async def test_m2_hole_without_tee_needs_it(client: AsyncClient):
    """
    GIVEN: Un campo sin mapa
    WHEN: Se marca solo el green
    THEN: 422 TEE_REQUIRED
    """
    course_id, _, _, player = await _scenario(client, "m2c")

    response = await _as(client, player).put(_url(course_id), json={"green_center": GREEN})

    assert response.status_code == 422
    assert response.json()["error_code"] == "TEE_REQUIRED"


# ============================================================================
# M3 — Errores
# ============================================================================


@pytest.mark.asyncio
async def test_m3_unknown_course_is_404(client: AsyncClient):
    """
    GIVEN: Un id que no es de ningún campo
    WHEN: Se marca o se piden las mías
    THEN: 404 GOLF_COURSE_NOT_FOUND en los dos
    """
    _, _, _, player = await _scenario(client, "m3a")
    nadie = str(GolfCourseId.generate())
    c = _as(client, player)

    for response in (
        await c.put(_url(nadie), json={"tee": SALIDA, "green_center": GREEN}),
        await c.get(_mine(nadie)),
    ):
        assert response.status_code == 404
        assert response.json()["error_code"] == "GOLF_COURSE_NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize("hole", [0, 19])
async def test_m3_hole_not_in_course_is_422(client: AsyncClient, hole):
    """
    GIVEN: Un campo de 18 hoyos
    WHEN: Se marca el 0 o el 19
    THEN: 422 HOLE_NOT_IN_COURSE
    """
    course_id, _, _, player = await _scenario(client, f"m3b{hole}")

    response = await _as(client, player).put(
        _url(course_id, hole), json={"tee": SALIDA, "green_center": GREEN}
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "HOLE_NOT_IN_COURSE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "error_code"),
    [
        (
            {"tee": SALIDA, "green_center": {"latitude": 36.2801, "longitude": -5.33}},
            "HOLE_MARK_OUT_OF_RANGE",
        ),
        ({"tee": {"latitude": 91, "longitude": 0}, "green_center": GREEN}, "INVALID_HOLE_MARK"),
        ({"tee": SALIDA, "bends": [CODO, CODO, CODO], "green_center": GREEN}, "INVALID_HOLE_MARK"),
    ],
)
async def test_m3_impossible_marks_are_422_with_their_code(client: AsyncClient, body, error_code):
    """
    GIVEN: Un green a 11 m de la salida, una latitud de 91 o tres codos
    WHEN: Se marca
    THEN: 422 con su código, y no se guarda nada
    """
    course_id, _, _, player = await _scenario(client, f"m3c{len(str(body))}")
    c = _as(client, player)

    response = await c.put(_url(course_id), json=body)

    assert response.status_code == 422
    assert response.json()["error_code"] == error_code
    assert (await c.get(_mine(course_id))).json() == []


@pytest.mark.asyncio
async def test_m3_far_from_the_course_is_422(client: AsyncClient):
    """
    GIVEN: Un campo con ubicación a ~5 km de la marca
    WHEN: Se marca
    THEN: 422 HOLE_MARK_TOO_FAR_FROM_COURSE
    """
    course_id, _, _, player = await _scenario(client, "m3d")
    await _place_course(course_id, 36.33, -5.33)

    response = await _as(client, player).put(
        _url(course_id), json={"tee": SALIDA, "green_center": GREEN}
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "HOLE_MARK_TOO_FAR_FROM_COURSE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"tee": SALIDA, "green_center": GREEN, "outline": []},
        {"tee": SALIDA},
        {"tee": [36.28, -5.33], "green_center": GREEN},
        {"tee": SALIDA, "bends": [CODO] * 21, "green_center": GREEN},
        {"tee": SALIDA, "green_center": GREEN, "marked_at": "2026-10-15T10:00:00"},
    ],
)
async def test_m3_malformed_bodies_are_422(client: AsyncClient, body):
    """
    GIVEN: Un campo de más, sin green, un punto como lista, 21 codos (un cuerpo
           absurdo se corta en la entrada) o `marked_at` sin zona horaria
    WHEN: Se marca
    THEN: 422 de validación
    """
    course_id, _, _, player = await _scenario(client, f"m3e{len(str(body))}")

    response = await _as(client, player).put(_url(course_id), json=body)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_m3_needs_a_session_and_valid_ids(client: AsyncClient):
    """
    GIVEN: Sin sesión, o con un id de campo o un hoyo que no son válidos
    WHEN: Se marca o se piden las mías
    THEN: 401, y 422
    """
    course_id, _, _, player = await _scenario(client, "m3f")
    body = {"tee": SALIDA, "green_center": GREEN}

    client.cookies.clear()
    assert (await client.put(_url(course_id), json=body)).status_code == 401
    assert (await client.get(_mine(course_id))).status_code == 401
    c = _as(client, player)
    assert (await c.put(_url("no-es-un-id"), json=body)).status_code == 422
    assert (await c.put(_url(course_id, "uno"), json=body)).status_code == 422


@pytest.mark.asyncio
async def test_m4_courses_players_cannot_see_are_404(client: AsyncClient):
    """
    GIVEN: Un campo pendiente de aprobar
    WHEN: Un jugador lo marca o pide sus marcas
    THEN: 404 GOLF_COURSE_NOT_FOUND, como si no existiera
    """
    creator = await create_authenticated_user(
        client, "creator-m4@test.com", "P@ssw0rd123!", "Creator", "Map"
    )
    course = await create_golf_course(client, creator["cookies"])
    player = await create_authenticated_user(
        client, "player-m4@test.com", "P@ssw0rd123!", "Player", "Map"
    )
    c = _as(client, player)

    for response in (
        await c.put(_url(course["id"]), json={"tee": SALIDA, "green_center": GREEN}),
        await c.get(_mine(course["id"])),
    ):
        assert response.status_code == 404
        assert response.json()["error_code"] == "GOLF_COURSE_NOT_FOUND"


@pytest.mark.asyncio
async def test_m5_a_late_mark_from_the_queue_does_not_replace_a_newer_one(client: AsyncClient):
    """
    GIVEN: El jugador marcó el hoyo 1 a las 10:05 (con red)
    WHEN: Llega de la cola la que hizo a las 10:00 sin cobertura
    THEN: 200 con la de las 10:05, que es la que queda
    """
    course_id, _, _, player = await _scenario(client, "m5")
    c = _as(client, player)
    nueva = {"tee": SALIDA, "bends": [CODO], "green_center": GREEN}
    await c.put(_url(course_id), json={**nueva, "marked_at": "2026-10-15T10:05:00+02:00"})

    response = await c.put(
        _url(course_id),
        json={"tee": SALIDA, "green_center": GREEN, "marked_at": "2026-10-15T10:00:00+02:00"},
    )

    assert response.status_code == 200
    assert response.json()["bends"] == [CODO]
    assert response.json()["marked_at"] == "2026-10-15T08:05:00Z"
    (mark,) = (await c.get(_mine(course_id))).json()
    assert mark["bends"] == [CODO]
