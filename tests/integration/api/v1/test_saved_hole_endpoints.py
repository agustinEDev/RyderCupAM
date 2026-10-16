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

from tests.integration.api.v1.test_hole_map_endpoints import _as, _scenario
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
