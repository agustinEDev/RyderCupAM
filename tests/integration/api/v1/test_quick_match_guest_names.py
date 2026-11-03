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
    G3  invitado con nombres compuestos             | tal cual, sin partir ni recortar
    G4  los endpoints que devuelven la partida      | todos traen los dos campos
        | (POST /start, GET /{id}, GET /me)           |
    G5  vista compartida (quien no jugó)            | sin nombre ni apellidos del invitado
        | (en test_get_shared_quick_match_use_case)   |
"""

import pytest
from httpx import AsyncClient

from tests.integration.api.v1.test_quick_match_start_in_one_go_endpoint import (
    _amigo,
    _cuerpo,
    _escenario,
    _invitado,
)

COMPUESTO = {"first_name": "María José", "last_name": "de la Fuente"}


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


ESPERADOS = [
    (False, None, None),
    (True, "Ana", "Pérez", "Ana Pérez"),
    (False, None, None),
    (True, "María José", "de la Fuente", "María José de la Fuente"),
]


def _compara(participants: list) -> None:
    obtenidos = _nombres(participants)
    for (es_invitado, nombre, apellidos, *completo), real in zip(ESPERADOS, obtenidos, strict=True):
        assert real[:3] == (es_invitado, nombre, apellidos), real
        if completo:
            assert real[3] == completo[0], real


class TestGuestNames:
    @pytest.mark.asyncio
    async def test_g1_g2_g3_on_start(self, client: AsyncClient):
        partida = await _partida_con_invitados(client)

        _compara(partida["participants"])

    @pytest.mark.asyncio
    async def test_g4_on_the_detail(self, client: AsyncClient):
        partida = await _partida_con_invitados(client)

        detail = await client.get(f"/api/v1/quick-matches/{partida['id']}")

        assert detail.status_code == 200, detail.text
        _compara(detail.json()["participants"])

    @pytest.mark.asyncio
    async def test_g4_on_my_list(self, client: AsyncClient):
        partida = await _partida_con_invitados(client)

        mine = await client.get("/api/v1/quick-matches/me")

        assert mine.status_code == 200, mine.text
        [listada] = [m for m in mine.json()["quick_matches"] if m["id"] == partida["id"]]
        _compara(listada["participants"])
