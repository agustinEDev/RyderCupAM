"""
Tests de integración: la partida rápida devuelve el nombre y los apellidos del
invitado por separado (BE #717).

Para repetir una partida rápida con un toque (FE #1021), el asistente se
rellena con la partida que ya se tiene, y el invitado se creó con nombre y
apellidos. Antes solo llegaba `name` («Pepe Pérez»), y partirlo era adivinar
(«María José de la Fuente»). Tabla aprobada el 3 nov 2026:

    #   caso                                        | respuesta
    ----|---------------------------------------------|---------------------------------
    G1  invitado                                    | first_name y last_name; name igual
    G2  registrado                                  | first_name y last_name a null
    G3  invitado con nombres compuestos y espacios  | sin partir; sin los espacios de
        | en los extremos                             | los extremos (los quita el dominio)
    G4  POST /start, GET /{id} y GET /me            | los tres traen los dos campos (el
        |                                             | resto sale del mismo mapper)
    G5  vista compartida (quien no jugó)            | sin nombre ni apellidos del invitado
        | (caso de uso y endpoint /shared)            |
"""

import pytest
from httpx import AsyncClient

from tests.integration.api.v1.test_quick_match_start_in_one_go_endpoint import (
    _amigo,
    _cuerpo,
    _escenario,
    _invitado,
)

COMPUESTO = {"first_name": "  María José ", "last_name": " de la Fuente  "}


async def _partida_con_invitados(client: AsyncClient):
    creator, friend, course_id = await _escenario(client)
    response = await client.post(
        "/api/v1/quick-matches/start",
        json=_cuerpo(
            course_id,
            creator,
            match_format=None,
            scoring_format="STABLEFORD",
            participants=[_invitado(), _amigo(friend), _invitado(**COMPUESTO)],
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _nombres(participants: list) -> list:
    return [(p["is_guest"], p["first_name"], p["last_name"], p["name"]) for p in participants]


# En el orden en que se crearon: el creador, y luego la lista de la petición
ESPERADOS = [
    (False, None, None, "Creator Quick"),
    (True, "Ana", "Pérez", "Ana Pérez"),
    (False, None, None, "Friend Quick"),
    (True, "María José", "de la Fuente", "María José de la Fuente"),
]


def _compara(participants: list) -> None:
    assert _nombres(participants) == ESPERADOS


class TestGuestNames:
    @pytest.mark.asyncio
    async def test_start_with_guests_returns_their_first_and_last_name_apart(
        self, client: AsyncClient
    ):
        """
        Given: una partida con dos invitados (uno con nombres compuestos y espacios) y un amigo
        When: se crea e inicia
        Then: los invitados traen nombre y apellidos por separado; los registrados, nulos (G1-G3)
        """
        partida = await _partida_con_invitados(client)

        _compara(partida["participants"])

    @pytest.mark.asyncio
    async def test_detail_returns_the_guest_names_apart(self, client: AsyncClient):
        """
        Given: una partida con invitados
        When: se pide su detalle
        Then: trae los mismos nombres y apellidos (G4)
        """
        partida = await _partida_con_invitados(client)

        detail = await client.get(f"/api/v1/quick-matches/{partida['id']}")

        assert detail.status_code == 200, detail.text
        _compara(detail.json()["participants"])

    @pytest.mark.asyncio
    async def test_my_list_returns_the_guest_names_apart(self, client: AsyncClient):
        """
        Given: una partida con invitados
        When: se pide la lista de mis partidas
        Then: la partida trae los mismos nombres y apellidos (G4)
        """
        partida = await _partida_con_invitados(client)

        mine = await client.get("/api/v1/quick-matches/me")

        assert mine.status_code == 200, mine.text
        [listada] = [m for m in mine.json()["quick_matches"] if m["id"] == partida["id"]]
        _compara(listada["participants"])
