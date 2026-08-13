"""
Tests E2E de las tarjetas por salida.

Verifican el camino completo por la API de lo que se añadió para poder importar
los campos federados de la RFEG: color de barras, distancias por hoyo y
tarjetas que difieren entre salidas del mismo campo.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]


def build_holes(meters: int, pars: list[int] | None = None, shift_index: bool = False):
    """Construye la tarjeta de una salida."""
    pars = pars or PAR_72
    holes = []
    for i in range(18):
        stroke_index = i + 1
        if shift_index and i < 2:
            # Intercambia la dificultad de los dos primeros hoyos
            stroke_index = 2 - i
        holes.append(
            {
                "hole_number": i + 1,
                "par": pars[i],
                "stroke_index": stroke_index,
                "meters": meters,
            }
        )
    return holes


class TestTeeScorecards:
    """POST /api/v1/golf-courses/request con tarjeta por salida"""

    @pytest.mark.asyncio
    async def test_create_course_with_per_tee_scorecards(self, client: AsyncClient):
        """
        GIVEN: Un campo cuyas salidas tienen distancias y dificultades distintas
        WHEN: Se solicita por la API y se consulta después
        THEN: Cada salida conserva su color, sus metros y sus índices
        """
        # Given
        user = await create_authenticated_user(
            client, "scorecards@test.com", "P@ssw0rd123!", "Creator", "Test"
        )
        payload = {
            "name": "Campo con tarjetas por barra",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "color": "WHITE",
                    "tee_gender": "MALE",
                    "course_rating": 73.5,
                    "slope_rating": 135,
                    "holes": build_holes(meters=400),
                },
                {
                    "color": "RED",
                    "tee_gender": "FEMALE",
                    "course_rating": 70.0,
                    "slope_rating": 120,
                    "holes": build_holes(meters=300, shift_index=True),
                },
            ],
            "holes": [
                {"hole_number": i + 1, "par": PAR_72[i], "stroke_index": i + 1} for i in range(18)
            ],
        }

        # When
        response = await client.post(
            "/api/v1/golf-courses/request", json=payload, cookies=user["cookies"]
        )

        # Then
        assert response.status_code == 201, response.text
        course_id = response.json()["id"]

        detail = await client.get(
            f"/api/v1/golf-courses/{course_id}", cookies=user["cookies"]
        )
        assert detail.status_code == 200, detail.text
        tees = detail.json()["tees"]

        by_color = {tee["color"]: tee for tee in tees}
        assert set(by_color) == {"WHITE", "RED"}

        # Cada salida mantiene su distancia
        assert all(hole["meters"] == 400 for hole in by_color["WHITE"]["holes"])
        assert all(hole["meters"] == 300 for hole in by_color["RED"]["holes"])

        # Y su propia dificultad por hoyo
        assert [h["stroke_index"] for h in by_color["WHITE"]["holes"][:2]] == [1, 2]
        assert [h["stroke_index"] for h in by_color["RED"]["holes"][:2]] == [2, 1]

    @pytest.mark.asyncio
    async def test_tees_without_scorecard_inherit_the_course_one(self, client: AsyncClient):
        """
        GIVEN: Un campo creado con una única tarjeta, como se hacía hasta ahora
        WHEN: Se solicita por la API
        THEN: Cada salida hereda esa tarjeta

        Es el caso de compatibilidad: los clientes que no envían tarjeta por
        salida siguen funcionando igual.
        """
        # Given
        user = await create_authenticated_user(
            client, "inherit@test.com", "P@ssw0rd123!", "Creator", "Test"
        )
        payload = {
            "name": "Campo con tarjeta unica",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "color": "WHITE",
                    "tee_gender": "MALE",
                    "course_rating": 73.5,
                    "slope_rating": 135,
                },
                {
                    "color": "YELLOW",
                    "tee_gender": "MALE",
                    "course_rating": 71.0,
                    "slope_rating": 128,
                },
            ],
            "holes": [
                {"hole_number": i + 1, "par": PAR_72[i], "stroke_index": i + 1} for i in range(18)
            ],
        }

        # When
        response = await client.post(
            "/api/v1/golf-courses/request", json=payload, cookies=user["cookies"]
        )

        # Then
        assert response.status_code == 201, response.text
        course_id = response.json()["id"]

        detail = await client.get(
            f"/api/v1/golf-courses/{course_id}", cookies=user["cookies"]
        )
        tees = detail.json()["tees"]
        assert len(tees) == 2
        assert all(len(tee["holes"]) == 18 for tee in tees)

    @pytest.mark.asyncio
    async def test_pitch_and_putt_is_accepted(self, client: AsyncClient):
        """
        GIVEN: Un pitch & putt con par 54 y ratings por debajo de la escala WHS
        WHEN: Se solicita por la API
        THEN: Se acepta

        Antes quedaba fuera: el DTO exigía slope 55-155 y par de campo largo.
        """
        # Given
        user = await create_authenticated_user(
            client, "pitchputt@test.com", "P@ssw0rd123!", "Creator", "Test"
        )
        payload = {
            "name": "Pitch and Putt Municipal",
            "country_code": "ES",
            "course_type": "PITCH_AND_PUTT",
            "tees": [
                {
                    "tee_gender": "MALE",
                    "color": "GREEN",
                    "course_rating": 46.8,
                    "slope_rating": 47,
                },
                {
                    "color": "RED",
                    "tee_gender": "FEMALE",
                    "course_rating": 47.8,
                    "slope_rating": 53,
                },
            ],
            "holes": [
                {"hole_number": i + 1, "par": 3, "stroke_index": i + 1, "meters": 100}
                for i in range(18)
            ],
        }

        # When
        response = await client.post(
            "/api/v1/golf-courses/request", json=payload, cookies=user["cookies"]
        )

        # Then
        assert response.status_code == 201, response.text
        assert response.json()["total_par"] == 54

    @pytest.mark.asyncio
    async def test_other_color_without_identifier_is_rejected(self, client: AsyncClient):
        """
        GIVEN: Una salida sin color ni identificador
        WHEN: Se solicita por la API
        THEN: Se rechaza como error de validación (422)

        Sin identificador, dos salidas OTHER serían indistinguibles. La regla la
        hace cumplir el dominio; el DTO la comprueba antes para señalar el campo
        concreto en vez de devolver un rechazo genérico.
        """
        # Given
        user = await create_authenticated_user(
            client, "nocolor@test.com", "P@ssw0rd123!", "Creator", "Test"
        )
        payload = {
            "name": "Campo sin color ni nombre",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    # Sin color ni identificador: cae en OTHER, y así sería
                    # indistinguible de cualquier otra salida sin nombre
                    "tee_gender": "MALE",
                    "course_rating": 73.5,
                    "slope_rating": 135,
                },
                {
                    "color": "YELLOW",
                    "tee_gender": "MALE",
                    "course_rating": 71.0,
                    "slope_rating": 128,
                },
            ],
            "holes": [
                {"hole_number": i + 1, "par": PAR_72[i], "stroke_index": i + 1} for i in range(18)
            ],
        }

        # When
        response = await client.post(
            "/api/v1/golf-courses/request", json=payload, cookies=user["cookies"]
        )

        # Then
        assert response.status_code == 422, response.text
        assert "identifier" in response.text
