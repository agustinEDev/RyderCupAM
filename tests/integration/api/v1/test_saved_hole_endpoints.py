"""
Integration tests de la línea que el admin guarda de cada hoyo (BE #575, 17 oct 2026).

| Caso | Qué                                             | Resultado                                  |
|------|-------------------------------------------------|--------------------------------------------|
| L1   | el admin guarda la línea de un hoyo             | 200, la línea; los jugadores la leen y el hoyo no recoge |
| L1   | un jugador manda una muestra de ese hoyo        | 204 y no se guarda                         |
| L2   | quien no es admin (guardar, reabrir, borrar)    | 403 ADMIN_REQUIRED                         |
| L3   | una línea imposible / un hoyo 19 / sin campo    | 422 INVALID_HOLE_LINE / 422 HOLE_NOT_IN_COURSE / 404 |
| L3   | un cuerpo con campos de más                     | 422                                        |
| L4   | reabrir                                         | 204; el hoyo vuelve a recoger              |
| L5   | borrar una muestra                              | 204 y se va; otra vez, 404 HOLE_SAMPLE_NOT_FOUND |
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import approve_golf_course, create_authenticated_user, create_golf_course
from tests.integration.api.v1.test_hole_map_endpoints import _as, _make_admin, _scenario
from tests.integration.api.v1.test_hole_sample_endpoints import (
    BODY,
    CODO,
    GREEN,
    SALIDA,
    _new,
    _rows,
)

LINEA = {"tee": SALIDA, "bends": [CODO], "green_center": GREEN}


def _line(course_id: str, hole: int | str = 1) -> str:
    return f"/api/v1/golf-courses/admin/{course_id}/hole-lines/{hole}"


def _samples(course_id: str) -> str:
    return f"/api/v1/golf-courses/{course_id}/hole-map/samples"


@pytest.mark.asyncio
async def test_l1_the_admin_saves_a_line_and_players_read_it(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "l1")

    response = await _as(client, admin).put(_line(course_id), json=LINEA)

    assert response.status_code == 200
    assert response.json() == LINEA
    hole = (await _as(client, player).get(_samples(course_id))).json()[0]
    assert hole["saved_line"] == LINEA
    assert hole["collecting"] is False


@pytest.mark.asyncio
async def test_l1_a_saved_hole_does_not_store_samples(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "l1b")
    await _as(client, admin).put(_line(course_id), json=LINEA)

    response = await _as(client, player).post(f"{_samples(course_id)}/1", json=_new(BODY))

    assert response.status_code == 204
    assert await _rows(course_id) == 0


@pytest.mark.asyncio
async def test_l2_only_admins(client: AsyncClient):
    course_id, _, _, player = await _scenario(client, "l2")
    c = _as(client, player)

    responses = [
        await c.put(_line(course_id), json=LINEA),
        await c.delete(_line(course_id)),
        await c.delete(f"/api/v1/golf-courses/admin/{course_id}/hole-samples/{uuid4()}"),
    ]

    assert [r.status_code for r in responses] == [403, 403, 403]
    assert {r.json()["error_code"] for r in responses} == {"ADMIN_REQUIRED"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url_hole", "body", "status", "code"),
    [
        pytest.param(
            1, {**LINEA, "bends": [CODO, CODO, CODO]}, 422, "INVALID_HOLE_LINE", id="tres codos"
        ),
        pytest.param(
            1,
            {**LINEA, "bends": [], "green_center": SALIDA},
            422,
            "INVALID_HOLE_LINE",
            id="green en la salida",
        ),
        pytest.param(19, LINEA, 422, "HOLE_NOT_IN_COURSE", id="hoyo 19"),
        pytest.param(
            1,
            {**LINEA, "bends": [], "green_center": {"latitude": 91, "longitude": -5.33}},
            422,
            "INVALID_HOLE_LINE",
            id="latitud 91",
        ),
    ],
)
async def test_l3_impossible_lines(client: AsyncClient, url_hole, body, status, code):
    course_id, admin, _, _ = await _scenario(client, f"l3{url_hole}{len(body['bends'])}")

    response = await _as(client, admin).put(_line(course_id, url_hole), json=body)

    assert (response.status_code, response.json()["error_code"]) == (status, code)


@pytest.mark.asyncio
async def test_l3_unknown_course_and_extra_fields(client: AsyncClient):
    _, admin, _, _ = await _scenario(client, "l3c")
    c = _as(client, admin)

    sin_campo = await c.put(_line(str(uuid4())), json=LINEA)
    de_mas = await c.put(_line(str(uuid4())), json={**LINEA, "par": 4})

    assert (sin_campo.status_code, sin_campo.json()["error_code"]) == (404, "GOLF_COURSE_NOT_FOUND")
    assert de_mas.status_code == 422


@pytest.mark.asyncio
async def test_l4_reopening_collects_again(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "l4")
    await _as(client, admin).put(_line(course_id), json=LINEA)

    response = await _as(client, admin).delete(_line(course_id))
    otra_vez = await _as(client, admin).delete(_line(course_id))

    assert (response.status_code, otra_vez.status_code) == (204, 204)
    hole = (await _as(client, player).get(_samples(course_id))).json()[0]
    assert (hole["saved_line"], hole["collecting"]) == (None, True)


@pytest.mark.asyncio
async def test_l5_deleting_a_sample(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "l5")
    sample = _new(BODY)
    await _as(client, player).post(f"{_samples(course_id)}/1", json=sample)
    url = f"/api/v1/golf-courses/admin/{course_id}/hole-samples/{sample['id']}"

    response = await _as(client, admin).delete(url)
    otra_vez = await _as(client, admin).delete(url)

    assert response.status_code == 204
    assert await _rows(course_id) == 0
    assert (otra_vez.status_code, otra_vez.json()["error_code"]) == (404, "HOLE_SAMPLE_NOT_FOUND")


@pytest.mark.asyncio
async def test_l5_a_sample_of_another_course_is_not_found(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "l5b")
    otro, _, _, _ = await _scenario(client, "l5c")
    sample = _new(BODY)
    await _as(client, player).post(f"{_samples(course_id)}/1", json=sample)

    response = await _as(client, admin).delete(
        f"/api/v1/golf-courses/admin/{otro}/hole-samples/{sample['id']}"
    )

    assert (response.status_code, response.json()["error_code"]) == (404, "HOLE_SAMPLE_NOT_FOUND")
    assert await _rows(course_id) == 1


@pytest.mark.asyncio
async def test_l5_deleting_on_an_unknown_course_is_404(client: AsyncClient):
    """CodeRabbit: sin recoger el error, un campo que no existe daba 500."""
    _, admin, _, _ = await _scenario(client, "l5d")

    response = await _as(client, admin).delete(
        f"/api/v1/golf-courses/admin/{uuid4()}/hole-samples/{uuid4()}"
    )

    assert (response.status_code, response.json()["error_code"]) == (404, "GOLF_COURSE_NOT_FOUND")


# ============================================================================
# R — Lo que lee el admin para revisar (BE #575)
# ============================================================================


@pytest.mark.asyncio
async def test_r1_the_list_and_a_course_to_review(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "r1")
    sample = _new(BODY)
    await _as(client, player).post(f"{_samples(course_id)}/1", json=sample)
    await _as(client, admin).put(_line(course_id, 2), json=LINEA)
    c = _as(client, admin)

    lista = await c.get("/api/v1/golf-courses/admin/hole-reviews")
    campo = await c.get(f"/api/v1/golf-courses/admin/{course_id}/hole-reviews")

    assert lista.status_code == 200
    (curso,) = [x for x in lista.json()["courses"] if x["golf_course_id"] == course_id]
    # El 2 está guardado: ya no está pendiente (17 oct). `saved` sigue, en false
    assert curso["holes"] == [{"hole_number": 1, "samples": 1, "saved": False}]
    assert campo.status_code == 200
    # La ubicación del campo, para marcar un hoyo sin nada (17 oct): el de la
    # prueba no tiene coordenadas, y viene null (el caso con ellas, en unitarios)
    assert campo.json()["location"] is None
    uno, dos = campo.json()["holes"][:2]
    assert [s["id"] for s in uno["samples"]] == [sample["id"]]
    assert (uno["samples"][0]["tee_color"], uno["samples"][0]["tee_gender"]) == ("YELLOW", "MALE")
    # Solo la muestra: nada de quién la mandó (no se guarda)
    assert set(uno["samples"][0]) == {
        "id",
        "tee_color",
        "tee_gender",
        "tee",
        "bends",
        "green_center",
        "received_on",
    }
    assert dos["saved_line"] == LINEA
    assert set(dos["saved_line"]) == {"tee", "bends", "green_center"}


@pytest.mark.asyncio
async def test_r3_saving_removes_a_hole_from_the_list_and_reopening_brings_it_back(
    client: AsyncClient,
):
    """Por la API y contra Postgres: guardar lo quita; reabrir con muestras lo devuelve (17 oct)."""
    course_id, admin, _, player = await _scenario(client, "r3")
    assert (
        await _as(client, player).post(f"{_samples(course_id)}/1", json=_new(BODY))
    ).status_code == 204
    c = _as(client, admin)

    def holes(response):
        return [
            h["hole_number"]
            for x in response.json()["courses"]
            if x["golf_course_id"] == course_id
            for h in x["holes"]
        ]

    assert holes(await c.get("/api/v1/golf-courses/admin/hole-reviews")) == [1]
    assert (await c.put(_line(course_id, 1), json=LINEA)).status_code in (200, 204)
    assert holes(await c.get("/api/v1/golf-courses/admin/hole-reviews")) == []
    assert (await c.delete(_line(course_id, 1))).status_code in (200, 204)
    assert holes(await c.get("/api/v1/golf-courses/admin/hole-reviews")) == [1]


@pytest.mark.asyncio
async def test_r4_a_course_with_coordinates_brings_its_location(client: AsyncClient):
    """
    GIVEN: un campo aprobado con coordenadas
    WHEN: el admin pide su revisión
    THEN: viene su ubicación, como punto
    """
    creator = await create_authenticated_user(
        client, "creator-r4@test.com", "P@ssw0rd123!", "Creator", "Map"
    )
    course = await create_golf_course(
        client,
        creator["cookies"],
        {
            "name": "Campo con coordenadas r4",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "location": {"latitude": 36.28, "longitude": -5.33},
            "tees": [
                {
                    "identifier": "Amarillo",
                    "color": "YELLOW",
                    "tee_gender": "MALE",
                    "course_rating": 70.2,
                    "slope_rating": 128,
                    "par": 72,
                }
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        },
    )
    admin = await create_authenticated_user(
        client, "admin-r4@test.com", "AdminPass123!", "Admin", "Map"
    )
    await _make_admin("admin-r4@test.com")
    await approve_golf_course(client, admin["cookies"], course["id"])

    campo = await _as(client, admin).get(f"/api/v1/golf-courses/admin/{course['id']}/hole-reviews")

    assert campo.status_code == 200
    assert campo.json()["location"] == {"latitude": 36.28, "longitude": -5.33}


@pytest.mark.asyncio
async def test_r2_only_admins_and_unknown_course(client: AsyncClient):
    course_id, admin, _, player = await _scenario(client, "r2")

    lista = await _as(client, player).get("/api/v1/golf-courses/admin/hole-reviews")
    campo = await _as(client, player).get(f"/api/v1/golf-courses/admin/{course_id}/hole-reviews")
    sin_campo = await _as(client, admin).get(f"/api/v1/golf-courses/admin/{uuid4()}/hole-reviews")

    assert [lista.status_code, campo.status_code] == [403, 403]
    assert (sin_campo.status_code, sin_campo.json()["error_code"]) == (404, "GOLF_COURSE_NOT_FOUND")
