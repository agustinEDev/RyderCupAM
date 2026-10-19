"""
Integration tests de los reportes de hoyo (entrega 7, aprobada el 18 oct 2026).

| Caso | Qué                                                   | Resultado                                    |
|------|-------------------------------------------------------|----------------------------------------------|
| E1   | un jugador reporta un hoyo con línea guardada         | 204 y se guarda, con su motivo               |
| E1   | un hoyo con línea del mapa de OSM aprobado            | 204 y se guarda                              |
| E2   | un hoyo sin línea                                     | 204 y no se guarda                           |
| E3   | campo que no existe / hoyo 19 / cuerpo malo           | 404 / 422 HOLE_NOT_IN_COURSE / 422           |
| E4   | sin sesión                                            | 401                                          |
| E5   | el admin: lista con `reports`, revisión con `reports` | el hoyo pendiente y su reporte, sin autor    |
| E6   | el admin descarta un reporte                          | 204; otra vez, 404 HOLE_REPORT_NOT_FOUND     |
| E7   | quien no es admin descarta                            | 403 ADMIN_REQUIRED                           |
| E8   | el admin guarda la línea del hoyo reportado           | sus reportes se cierran y sale de la lista   |
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.api.v1.test_hole_map_endpoints import (
    _as,
    _in_db,
    _save_map,
    _scenario,
)
from tests.integration.api.v1.test_hole_sample_endpoints import CODO, GREEN, SALIDA

LINEA = {"tee": SALIDA, "bends": [], "green_center": GREEN}


def _report(reason: str = "WRONG_LINE", **extra) -> dict:
    return {"id": str(uuid4()), "reason": reason, **LINEA, **extra}


def _reports(course_id: str, hole: int | str = 1) -> str:
    return f"/api/v1/golf-courses/{course_id}/hole-map/reports/{hole}"


def _line(course_id: str, hole: int = 1) -> str:
    return f"/api/v1/golf-courses/admin/{course_id}/hole-lines/{hole}"


async def _rows(course_id: str, hole: int = 1) -> list[tuple]:
    async def work(session):
        return (
            await session.execute(
                text(
                    "SELECT reason, jsonb_array_length(bends) FROM golf_course_hole_reports "
                    "WHERE golf_course_id = :id AND hole_number = :hole ORDER BY seq"
                ),
                {"id": course_id, "hole": hole},
            )
        ).all()

    return await _in_db(work)


@pytest.mark.asyncio
async def test_e1_a_player_reports_a_hole_with_a_saved_line(client: AsyncClient):
    """
    GIVEN: Un hoyo con la línea guardada por el admin
    WHEN: Un jugador lo reporta con «El hoyo ha cambiado» y un codo
    THEN: 204, y se guarda con su motivo
    """
    course_id, admin, _, player = await _scenario(client, "r-e1")
    await _as(client, admin).put(_line(course_id), json=LINEA)

    response = await _as(client, player).post(
        _reports(course_id), json=_report("HOLE_CHANGED", bends=[CODO])
    )

    assert response.status_code == 204
    assert await _rows(course_id) == [("HOLE_CHANGED", 1)]


@pytest.mark.asyncio
async def test_e1_a_hole_of_the_approved_osm_map_can_be_reported(client: AsyncClient):
    """
    GIVEN: Un campo con su mapa de OSM aprobado (el hoyo 1 con línea)
    WHEN: Un jugador reporta el hoyo 1
    THEN: Se guarda
    """
    course_id, _, admin_email, player = await _scenario(client, "r-e1o")
    await _save_map(course_id, approved_by_email=admin_email)

    response = await _as(client, player).post(_reports(course_id), json=_report("WRONG_HOLE"))

    assert response.status_code == 204
    assert await _rows(course_id) == [("WRONG_HOLE", 0)]


@pytest.mark.asyncio
async def test_e2_a_hole_without_a_line_is_not_reported(client: AsyncClient):
    """
    GIVEN: Un hoyo sin línea
    WHEN: Un jugador lo reporta
    THEN: 204 igual, y no se guarda
    """
    course_id, _, _, player = await _scenario(client, "r-e2")

    response = await _as(client, player).post(_reports(course_id), json=_report())

    assert response.status_code == 204
    assert await _rows(course_id) == []


@pytest.mark.asyncio
async def test_e3_unknown_course_bad_hole_and_bad_body(client: AsyncClient):
    """
    GIVEN: Un campo que no existe, un hoyo 19, un motivo que no existe, sin salida
           y un campo de más
    WHEN: Se reporta
    THEN: 404 GOLF_COURSE_NOT_FOUND, 422 HOLE_NOT_IN_COURSE y 422 los cuerpos malos
    """
    course_id, _, _, player = await _scenario(client, "r-e3")
    c = _as(client, player)

    sin_campo = await c.post(_reports(str(uuid4())), json=_report())
    hoyo_19 = await c.post(_reports(course_id, 19), json=_report())
    malos = [
        await c.post(_reports(course_id), json=_report("OTHER")),
        await c.post(_reports(course_id), json={k: v for k, v in _report().items() if k != "tee"}),
        await c.post(_reports(course_id), json=_report(tee_color="YELLOW")),
    ]

    assert (sin_campo.status_code, sin_campo.json()["error_code"]) == (404, "GOLF_COURSE_NOT_FOUND")
    assert (hoyo_19.status_code, hoyo_19.json()["error_code"]) == (422, "HOLE_NOT_IN_COURSE")
    assert [r.status_code for r in malos] == [422, 422, 422]


@pytest.mark.asyncio
async def test_e4_a_session_is_required(client: AsyncClient):
    """
    GIVEN: Nadie con sesión
    WHEN: Se reporta un hoyo
    THEN: 401
    """
    course_id, _, _, _ = await _scenario(client, "r-e4")
    client.cookies.clear()

    response = await client.post(_reports(course_id), json=_report())

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_e5_the_admin_sees_the_reported_hole_and_its_report(client: AsyncClient):
    """
    GIVEN: Un hoyo guardado y reportado
    WHEN: El admin lee la lista y la revisión del campo
    THEN: El hoyo está pendiente con reports=1, y la revisión trae el reporte sin autor
    """
    course_id, admin, _, player = await _scenario(client, "r-e5")
    await _as(client, admin).put(_line(course_id), json=LINEA)
    body = _report("WRONG_LINE", bends=[CODO])
    await _as(client, player).post(_reports(course_id), json=body)

    lista = (await _as(client, admin).get("/api/v1/golf-courses/admin/hole-reviews")).json()
    revision = (
        await _as(client, admin).get(f"/api/v1/golf-courses/admin/{course_id}/hole-reviews")
    ).json()

    [campo] = [c for c in lista["courses"] if c["golf_course_id"] == course_id]
    assert [(h["hole_number"], h["samples"], h["reports"]) for h in campo["holes"]] == [(1, 0, 1)]
    [reporte] = revision["holes"][0]["reports"]
    assert set(reporte) == {"id", "reason", "tee", "bends", "green_center", "received_on"}
    assert (reporte["id"], reporte["reason"], reporte["bends"]) == (
        body["id"],
        "WRONG_LINE",
        [CODO],
    )
    assert revision["holes"][1]["reports"] == []


@pytest.mark.asyncio
async def test_e6_the_admin_discards_a_report(client: AsyncClient):
    """
    GIVEN: Un hoyo reportado
    WHEN: El admin descarta el reporte, y otra vez
    THEN: 204 y se va; la segunda, 404 HOLE_REPORT_NOT_FOUND
    """
    course_id, admin, _, player = await _scenario(client, "r-e6")
    await _as(client, admin).put(_line(course_id), json=LINEA)
    body = _report()
    await _as(client, player).post(_reports(course_id), json=body)
    url = f"/api/v1/golf-courses/admin/{course_id}/hole-reports/{body['id']}"

    primera = await _as(client, admin).delete(url)
    segunda = await _as(client, admin).delete(url)

    assert primera.status_code == 204
    assert await _rows(course_id) == []
    assert (segunda.status_code, segunda.json()["error_code"]) == (404, "HOLE_REPORT_NOT_FOUND")


@pytest.mark.asyncio
async def test_e7_only_admins_discard(client: AsyncClient):
    """
    GIVEN: Un jugador que no es admin
    WHEN: Descarta un reporte
    THEN: 403 ADMIN_REQUIRED
    """
    course_id, _, _, player = await _scenario(client, "r-e7")

    response = await _as(client, player).delete(
        f"/api/v1/golf-courses/admin/{course_id}/hole-reports/{uuid4()}"
    )

    assert (response.status_code, response.json()["error_code"]) == (403, "ADMIN_REQUIRED")


@pytest.mark.asyncio
async def test_e8_saving_the_line_closes_the_reports(client: AsyncClient):
    """
    GIVEN: Un hoyo guardado y reportado
    WHEN: El admin vuelve a guardar su línea
    THEN: El reporte se cierra y el campo sale de la lista
    """
    course_id, admin, _, player = await _scenario(client, "r-e8")
    await _as(client, admin).put(_line(course_id), json=LINEA)
    await _as(client, player).post(_reports(course_id), json=_report())

    await _as(client, admin).put(_line(course_id), json={**LINEA, "bends": [CODO]})

    assert await _rows(course_id) == []
    lista = (await _as(client, admin).get("/api/v1/golf-courses/admin/hole-reviews")).json()
    assert [c for c in lista["courses"] if c["golf_course_id"] == course_id] == []
