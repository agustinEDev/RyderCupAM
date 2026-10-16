"""
Integration tests de los endpoints del mapa de hoyos (BE #532).

- GET  /api/v1/golf-courses/{id}/hole-map                     (cualquier usuario)
- GET  /api/v1/golf-courses/admin/hole-maps/pending           (admin)
- GET  /api/v1/golf-courses/admin/{id}/hole-map               (admin)
- PUT  /api/v1/golf-courses/admin/{id}/hole-map/approve|reject (admin)

Los errores llevan un código fijo (`error_code`): el front decide por él, y el
texto de la excepción no sale nunca en la respuesta.
"""

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.infrastructure.persistence.repositories.hole_map_repository import (
    HoleMapRepository,
)
from tests.conftest import approve_golf_course, create_authenticated_user, create_golf_course

IMPORTADO = datetime(2026, 10, 15, 9, 0, 0, 123456)
VERSION = "2026-10-15T09:00:00.123456Z"


async def _in_db(work):
    """Ejecuta `work(session)` con la sesión de la app de tests y confirma."""
    from main import app as fastapi_app
    from src.config.dependencies import get_db_session

    override = fastapi_app.dependency_overrides.get(get_db_session)
    async for session in override():
        try:
            result = await work(session)
            await session.commit()
            return result
        finally:
            await session.close()
    return None


async def _make_admin(email: str) -> None:
    async def work(session):
        await session.execute(
            text("UPDATE users SET is_admin = true WHERE email = :email"), {"email": email}
        )

    await _in_db(work)


async def _save_map(course_id: str, *, approved_by_email: str | None = None) -> None:
    """Un mapa pendiente (hoyo 1 con green de OSM, hoyo 2 sin green); aprobado si se pide."""

    async def work(session):
        hole_map = CourseHoleMap.create(
            golf_course_id=GolfCourseId(course_id),
            holes=[
                MappedHole(
                    number=1,
                    play_line=(
                        GeoPoint(latitude=36.28, longitude=-5.33),
                        GeoPoint(latitude=36.29, longitude=-5.332),
                    ),
                    line_source=PositionSource.OSM,
                    green=GreenPosition(
                        front=GeoPoint(latitude=36.2898, longitude=-5.3321),
                        center=GeoPoint(latitude=36.29, longitude=-5.332),
                        back=GeoPoint(latitude=36.2902, longitude=-5.3319),
                        outline=(
                            GeoPoint(latitude=36.2897, longitude=-5.3323),
                            GeoPoint(latitude=36.2903, longitude=-5.3323),
                            GeoPoint(latitude=36.2903, longitude=-5.3317),
                        ),
                        source=PositionSource.OSM,
                    ),
                ),
                MappedHole(
                    number=2,
                    play_line=(
                        GeoPoint(latitude=36.291, longitude=-5.332),
                        GeoPoint(latitude=36.295, longitude=-5.335),
                    ),
                    line_source=PositionSource.OSM,
                ),
            ],
            osm_reference="way/237391513",
            imported_at=IMPORTADO,
        )
        if approved_by_email is not None:
            from src.modules.user.domain.value_objects.user_id import UserId

            row = await session.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": approved_by_email}
            )
            hole_map.approve(reviewer_id=UserId(uuid.UUID(row.scalar_one())))
        await HoleMapRepository(session).save(hole_map)

    await _in_db(work)


async def _scenario(client: AsyncClient, tag: str):
    """Un campo aprobado, un admin y un jugador cualquiera."""
    creator = await create_authenticated_user(
        client, f"creator-{tag}@test.com", "P@ssw0rd123!", "Creator", "Map"
    )
    course = await create_golf_course(client, creator["cookies"])
    admin_email = f"admin-{tag}@test.com"
    admin = await create_authenticated_user(client, admin_email, "AdminPass123!", "Admin", "Map")
    await _make_admin(admin_email)
    await approve_golf_course(client, admin["cookies"], course["id"])
    player = await create_authenticated_user(
        client, f"player-{tag}@test.com", "P@ssw0rd123!", "Player", "Map"
    )
    return course["id"], admin, admin_email, player


def _as(client: AsyncClient, user: dict) -> AsyncClient:
    client.cookies.clear()
    client.cookies.update(user["cookies"])
    return client


# ============================================================================
# P — Mapa para el jugador
# ============================================================================


@pytest.mark.asyncio
async def test_p1_any_player_gets_the_approved_map(client: AsyncClient):
    """
    GIVEN: Un campo con su mapa aprobado
    WHEN: Un jugador cualquiera pide el mapa
    THEN: 200 con el GeoJSON ([lon, lat]), la versión y la atribución de OSM
    """
    course_id, _, admin_email, player = await _scenario(client, "p1")
    await _save_map(course_id, approved_by_email=admin_email)

    response = await _as(client, player).get(f"/api/v1/golf-courses/{course_id}/hole-map")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["version"] == VERSION
    assert data["attribution"] == "© OpenStreetMap contributors (ODbL)"
    assert data["holes_needing_green"] == [2]
    line = next(f for f in data["geojson"]["features"] if f["properties"]["kind"] == "play_line")
    assert line["geometry"]["coordinates"][0] == [-5.33, 36.28]
    kinds = sorted(f["properties"]["kind"] for f in data["geojson"]["features"])
    assert kinds == [
        "green_back",
        "green_center",
        "green_front",
        "green_outline",
        "play_line",
        "play_line",
    ]


@pytest.mark.asyncio
async def test_p2_pending_map_is_404_even_for_an_admin(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente
    WHEN: Un jugador, y también un admin, piden el mapa público
    THEN: 404 HOLE_MAP_NOT_FOUND
    """
    course_id, admin, _, player = await _scenario(client, "p2")
    await _save_map(course_id)

    for user in (player, admin):
        response = await _as(client, user).get(f"/api/v1/golf-courses/{course_id}/hole-map")
        assert response.status_code == 404
        assert response.json()["error_code"] == "HOLE_MAP_NOT_FOUND"


@pytest.mark.asyncio
async def test_p3_course_without_map_or_unknown_is_404(client: AsyncClient):
    """
    GIVEN: Un campo sin mapa, y un id que no es de ningún campo
    WHEN: Se pide su mapa
    THEN: 404 HOLE_MAP_NOT_FOUND en los dos
    """
    course_id, _, _, player = await _scenario(client, "p3")

    for target in (course_id, str(GolfCourseId.generate())):
        response = await _as(client, player).get(f"/api/v1/golf-courses/{target}/hole-map")
        assert response.status_code == 404
        assert response.json()["error_code"] == "HOLE_MAP_NOT_FOUND"


@pytest.mark.asyncio
async def test_p4_needs_a_session_and_a_valid_id(client: AsyncClient):
    """
    GIVEN: Sin sesión, o con un id que no es UUID
    WHEN: Se pide el mapa
    THEN: 401 y 422
    """
    course_id, _, _, player = await _scenario(client, "p4")

    client.cookies.clear()
    assert (await client.get(f"/api/v1/golf-courses/{course_id}/hole-map")).status_code == 401
    response = await _as(client, player).get("/api/v1/golf-courses/no-es-un-id/hole-map")
    assert response.status_code == 422


# ============================================================================
# A — Revisión del admin
# ============================================================================


@pytest.mark.asyncio
async def test_a_non_admin_gets_403_everywhere(client: AsyncClient):
    """
    GIVEN: Un jugador que no es admin y un mapa pendiente
    WHEN: Usa cualquiera de los endpoints de admin
    THEN: 403 en todos
    """
    course_id, _, _, player = await _scenario(client, "a0")
    await _save_map(course_id)
    c = _as(client, player)

    assert (await c.get("/api/v1/golf-courses/admin/hole-maps/pending")).status_code == 403
    assert (await c.get(f"/api/v1/golf-courses/admin/{course_id}/hole-map")).status_code == 403
    for action in ("approve", "reject"):
        response = await c.put(
            f"/api/v1/golf-courses/admin/{course_id}/hole-map/{action}", json={"version": VERSION}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_a1_admin_lists_pending_maps(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin pide los pendientes
    THEN: Sale con el nombre del campo, hoyos, hoyos sin green, fecha y referencia
    """
    course_id, admin, _, _ = await _scenario(client, "a1")
    await _save_map(course_id)

    response = await _as(client, admin).get("/api/v1/golf-courses/admin/hole-maps/pending")

    assert response.status_code == 200
    (item,) = [i for i in response.json() if i["golf_course_id"] == course_id]
    assert item["golf_course_name"]
    assert item["holes"] == 2
    assert item["holes_needing_green"] == 1
    assert item["osm_reference"] == "way/237391513"
    assert item["imported_at"] == "2026-10-15T09:00:00.123456Z"
    assert item["version"] == VERSION


@pytest.mark.asyncio
async def test_a2_admin_gets_a_pending_map_to_review(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente, y un campo sin mapa
    WHEN: El admin pide cada uno para revisarlo
    THEN: 200 con el pendiente (estado y referencia); 404 el que no tiene
    """
    course_id, admin, _, _ = await _scenario(client, "a2")
    await _save_map(course_id)
    c = _as(client, admin)

    response = await c.get(f"/api/v1/golf-courses/admin/{course_id}/hole-map")
    missing = await c.get(f"/api/v1/golf-courses/admin/{GolfCourseId.generate()}/hole-map")

    assert response.status_code == 200
    assert response.json()["status"] == "PENDING_REVIEW"
    assert response.json()["osm_reference"] == "way/237391513"
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "HOLE_MAP_NOT_FOUND"


@pytest.mark.asyncio
async def test_a3_approve_with_the_seen_version_publishes_it(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin lo aprueba con la versión que vio
    THEN: 200 aprobado, y desde ese momento el jugador lo ve
    """
    course_id, admin, _, player = await _scenario(client, "a3")
    await _save_map(course_id)

    response = await _as(client, admin).put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/approve", json={"version": VERSION}
    )
    public = await _as(client, player).get(f"/api/v1/golf-courses/{course_id}/hole-map")

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["reviewed_by"]
    assert public.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_a4_other_version_is_409_changed(client: AsyncClient, action):
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin lo aprueba o rechaza con una versión que no es la actual
    THEN: 409 HOLE_MAP_CHANGED y sigue pendiente
    """
    course_id, admin, _, _ = await _scenario(client, f"a4{action}")
    await _save_map(course_id)
    c = _as(client, admin)

    response = await c.put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/{action}",
        json={"version": "2026-10-15T09:00:00.123455Z"},
    )
    after = await c.get(f"/api/v1/golf-courses/admin/{course_id}/hole-map")

    assert response.status_code == 409
    assert response.json()["error_code"] == "HOLE_MAP_CHANGED"
    assert after.json()["status"] == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_a5_already_reviewed_is_409_not_pending(client: AsyncClient):
    """
    GIVEN: Un mapa ya aprobado
    WHEN: El admin intenta rechazarlo
    THEN: 409 HOLE_MAP_NOT_PENDING
    """
    course_id, admin, admin_email, _ = await _scenario(client, "a5")
    await _save_map(course_id, approved_by_email=admin_email)

    response = await _as(client, admin).put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/reject", json={"version": VERSION}
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "HOLE_MAP_NOT_PENDING"


@pytest.mark.asyncio
async def test_a6_reject_with_reason_and_too_long_reason(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin lo rechaza con un motivo de 501 caracteres y luego con uno bueno
    THEN: 400 INVALID_REJECTION_REASON sin tocarlo; después 200 rechazado con su motivo
    """
    course_id, admin, _, _ = await _scenario(client, "a6")
    await _save_map(course_id)
    c = _as(client, admin)
    url = f"/api/v1/golf-courses/admin/{course_id}/hole-map/reject"

    too_long = await c.put(url, json={"version": VERSION, "reason": "x" * 501})
    untouched = (await c.get(f"/api/v1/golf-courses/admin/{course_id}/hole-map")).json()
    response = await c.put(url, json={"version": VERSION, "reason": "Hoyos de otro recorrido"})

    assert too_long.status_code == 400
    assert too_long.json()["error_code"] == "INVALID_REJECTION_REASON"
    assert untouched["status"] == "PENDING_REVIEW"
    assert untouched["rejection_reason"] is None
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "Hoyos de otro recorrido"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_a7_review_of_missing_map_is_404(client: AsyncClient, action):
    """
    GIVEN: Un campo sin mapa
    WHEN: El admin lo aprueba o rechaza
    THEN: 404 HOLE_MAP_NOT_FOUND
    """
    course_id, admin, _, _ = await _scenario(client, f"a7{action}")

    response = await _as(client, admin).put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/{action}", json={"version": VERSION}
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "HOLE_MAP_NOT_FOUND"


@pytest.mark.asyncio
async def test_a9_errors_never_echo_the_exception_text(client: AsyncClient):
    """
    GIVEN: Un 409 por versión cambiada
    WHEN: Se mira la respuesta
    THEN: El mensaje es fijo: no lleva ni el id del campo ni las fechas comparadas
    """
    course_id, admin, _, _ = await _scenario(client, "a9")
    await _save_map(course_id)

    response = await _as(client, admin).put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/approve",
        json={"version": "2026-01-01T00:00:00Z"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "HOLE_MAP_CHANGED"
    detail = response.json()["detail"]
    assert course_id not in detail
    assert "2026" not in detail


@pytest.mark.asyncio
async def test_a3_version_echoed_verbatim_from_the_review_screen_is_accepted(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin aprueba devolviendo la versión tal como se la dio el GET
    THEN: 200; la versión viaja en UTC con «Z» y vuelve igual
    """
    course_id, admin, _, _ = await _scenario(client, "a3z")
    await _save_map(course_id)
    c = _as(client, admin)

    seen = (await c.get(f"/api/v1/golf-courses/admin/{course_id}/hole-map")).json()["version"]
    response = await c.put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/approve", json={"version": seen}
    )

    assert seen == "2026-10-15T09:00:00.123456Z"
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a9_unexpected_error_while_approving_is_a_500_not_a_400(client: AsyncClient):
    """
    GIVEN: Un fallo inesperado al aprobar (un ValueError que no es del motivo)
    WHEN: El admin aprueba
    THEN: 500 (lo ve Sentry), no «motivo de rechazo inválido»
    """
    from main import app as fastapi_app
    from src.config.dependencies import get_approve_hole_map_use_case

    course_id, admin, _, _ = await _scenario(client, "a9b")

    class Rompe:
        async def execute(self, *_args):
            raise ValueError("fila corrupta")

    fastapi_app.dependency_overrides[get_approve_hole_map_use_case] = Rompe
    try:
        response = await _as(client, admin).put(
            f"/api/v1/golf-courses/admin/{course_id}/hole-map/approve", json={"version": VERSION}
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_approve_hole_map_use_case, None)

    assert response.status_code == 500
    assert "fila corrupta" not in response.text


@pytest.mark.asyncio
async def test_a10_approve_does_not_take_a_reason(client: AsyncClient):
    """
    GIVEN: Un mapa pendiente
    WHEN: Se aprueba mandando también un motivo
    THEN: 422: el motivo es solo para rechazar, no se tira sin avisar
    """
    course_id, admin, _, _ = await _scenario(client, "a10")
    await _save_map(course_id)

    response = await _as(client, admin).put(
        f"/api/v1/golf-courses/admin/{course_id}/hole-map/approve",
        json={"version": VERSION, "reason": "el 7 tiene mal el green"},
    )

    assert response.status_code == 422
