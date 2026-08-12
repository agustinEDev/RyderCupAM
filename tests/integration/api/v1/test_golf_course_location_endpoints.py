"""
Tests E2E de la ubicación de los campos de golf.

Verifican el criterio de la issue #105: que la ubicación se pueda enviar al dar
de alta un campo y salga en la API al consultarlo, tanto en el detalle como en
el listado, que es de donde tirará la búsqueda por cercanía.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
)

DERIO_LOCATION = {
    "latitude": 43.29519,
    "longitude": -2.87352,
    "address": "CALLE EREAGA BIDEA S/N, 48160, DERIO, VIZCAYA",
    "city": "DERIO",
    "province": "VIZCAYA",
}


def build_course_payload(location: dict | None = None) -> dict:
    """Construye el cuerpo de un alta de campo, con o sin ubicación."""
    payload = {
        "name": "Campo con ubicación",
        "country_code": "ES",
        "course_type": "STANDARD_18",
        "tees": [
            {
                "color": "YELLOW",
                "tee_gender": "MALE",
                "course_rating": 70.2,
                "slope_rating": 128,
            }
        ],
        "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
    }
    if location is not None:
        payload["location"] = location
    return payload


class TestGolfCourseLocation:
    """Ubicación en el alta y la consulta de campos."""

    @pytest.mark.asyncio
    async def test_request_course_with_location_returns_it(self, client: AsyncClient):
        """Un campo dado de alta con ubicación la devuelve en la respuesta."""
        user = await create_authenticated_user(
            client, "location-creator@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        response = await client.post(
            "/api/v1/golf-courses/request",
            json=build_course_payload(DERIO_LOCATION),
            cookies=user["cookies"],
        )

        assert response.status_code == 201
        location = response.json()["location"]
        assert location["latitude"] == 43.29519
        assert location["longitude"] == -2.87352
        assert location["city"] == "DERIO"
        assert location["province"] == "VIZCAYA"

    @pytest.mark.asyncio
    async def test_request_course_without_location_returns_null(self, client: AsyncClient):
        """Un campo sin ubicación la devuelve como null, no como objeto vacío."""
        user = await create_authenticated_user(
            client, "no-location@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        response = await client.post(
            "/api/v1/golf-courses/request",
            json=build_course_payload(),
            cookies=user["cookies"],
        )

        assert response.status_code == 201
        assert response.json()["location"] is None

    @pytest.mark.asyncio
    async def test_half_coordinates_are_rejected(self, client: AsyncClient):
        """Enviar solo la latitud es un error de validación, no un campo a medias."""
        user = await create_authenticated_user(
            client, "half-coords@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        response = await client.post(
            "/api/v1/golf-courses/request",
            json=build_course_payload({"latitude": 43.29519}),
            cookies=user["cookies"],
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_impossible_latitude_is_rejected(self, client: AsyncClient):
        """Una latitud fuera del rango geográfico es un error de validación."""
        user = await create_authenticated_user(
            client, "bad-coords@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        response = await client.post(
            "/api/v1/golf-courses/request",
            json=build_course_payload({"latitude": 120.0, "longitude": 0.0}),
            cookies=user["cookies"],
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_location_survives_in_detail_and_list(self, client: AsyncClient):
        """La ubicación sale al consultar el campo y también al listarlo."""
        creator = await create_authenticated_user(
            client, "location-detail@test.com", "P@ssw0rd123!", "Creator", "Test"
        )
        created = await client.post(
            "/api/v1/golf-courses/request",
            json=build_course_payload(DERIO_LOCATION),
            cookies=creator["cookies"],
        )
        course_id = created.json()["id"]
        admin = await create_admin_user(
            client, "location-admin@test.com", "P@ssw0rd123!", "Admin", "Test"
        )
        await approve_golf_course(client, admin["cookies"], course_id)

        detail = await client.get(f"/api/v1/golf-courses/{course_id}", cookies=creator["cookies"])
        listing = await client.get("/api/v1/golf-courses", cookies=creator["cookies"])

        assert detail.status_code == 200
        assert detail.json()["location"]["city"] == "DERIO"

        assert listing.status_code == 200
        listed = next(
            course for course in listing.json()["golf_courses"] if course["id"] == course_id
        )
        assert listed["location"]["latitude"] == 43.29519
