"""
Cada lectura, solo las consultas que necesita (tabla del 27 oct 2026, PR 2).

Una privada de stroke play con sus partidas generadas, vista por quien la
organiza, por un aprobado y por alguien de fuera. En ninguna petición se hace
dos veces la misma consulta: lo que ya se leyó se pasa, no se vuelve a pedir.
Preguntas distintas a una misma tabla (contar los aprobados, buscar la mía) sí
(Agustín, 27 oct: la regla era «ninguna tabla dos veces»; medido, juntarlas
traería más datos de los que hacen falta).

  #    lectura                          | regla
  -----|---------------------------------|----------------------------------
  R1   ficha                            | ninguna consulta repetida
  R2   agenda                           | ninguna consulta repetida
  R3   grupos de una franja             | ninguna consulta repetida
  R4   lista de inscritos               | ninguna consulta repetida
  R5   anotación de un grupo            | ninguna consulta repetida
  R6   clasificación general            | ninguna consulta repetida
  R10  cada una, por quien mira         | no más sentencias que las de hoy
                                        | (tope medido el 27 oct 2026)
"""

import re
from collections import Counter

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_lo_jugado_de_una_privada_endpoints import (
    _con_dos_partidas,
    _jugador,
)

pytestmark = pytest.mark.asyncio


async def _consultas(client: AsyncClient, quien: dict, ruta: str) -> tuple[int, Counter]:
    """Cada consulta que llega a Postgres: el mismo texto con los mismos parámetros."""
    consultas: Counter = Counter()

    def _apunta(conn, cursor, statement, parameters, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            consultas[" ".join(statement.split()) + " " + repr(parameters)] += 1

    set_auth_cookies(client, quien["cookies"])
    event.listen(Engine, "before_cursor_execute", _apunta)
    try:
        respuesta = await client.get(ruta)
    finally:
        event.remove(Engine, "before_cursor_execute", _apunta)
    return respuesta.status_code, consultas


def _repetidas(consultas: Counter) -> dict:
    """Las repetidas, por su tabla, para que el fallo se lea."""
    repetidas: Counter = Counter()
    for texto, veces in consultas.items():
        if veces > 1:
            tabla = re.search(r"\bFROM\s+(\w+)", texto, re.I)
            repetidas[tabla.group(1) if tabla else texto[:60]] += veces
    return dict(repetidas)


@pytest.fixture
async def privada(client: AsyncClient):
    org, comp, franja, otros, grupos = await _con_dos_partidas(client)
    fuera = await _jugador(client, "Fuera")
    return {
        "quien": {"organizador": org, "aprobado": otros[0], "fuera": fuera},
        "rutas": {
            "R1 ficha": f"/api/v1/competitions/{comp['id']}",
            "R2 agenda": f"/api/v1/competitions/{comp['id']}/schedule",
            "R3 grupos": f"/api/v1/competitions/rounds/{franja}/groups",
            "R4 inscritos": f"/api/v1/competitions/{comp['id']}/enrollments",
            "R5 anotacion": f"/api/v1/competitions/groups/{grupos[0]['id']}/scoring-view",
            "R6 general": f"/api/v1/competitions/{comp['id']}/standings",
        },
    }


@pytest.mark.parametrize("quien", ["organizador", "aprobado", "fuera"])
async def test_ninguna_lectura_repite_consulta(client: AsyncClient, privada, quien):
    repetidas = {}
    for nombre, ruta in privada["rutas"].items():
        estado, consultas = await _consultas(client, privada["quien"][quien], ruta)
        assert estado in (200, 403), (nombre, estado)
        if sobran := _repetidas(consultas):
            repetidas[nombre] = sobran

    assert repetidas == {}, repetidas


# Sentencias de cada lectura, medidas tras la PR 2 (27 oct 2026). Antes:
# ficha 42/30/27, agenda 12/16/18, grupos 14/18/20, inscritos 8/12/11,
# anotación 21/22/11, general 17/18/9. Si una sube, alguien vuelve a leer de más
TOPES = {
    "R1 ficha": {"organizador": 22, "aprobado": 19, "fuera": 16},
    "R2 agenda": {"organizador": 12, "aprobado": 15, "fuera": 17},
    "R3 grupos": {"organizador": 14, "aprobado": 16, "fuera": 18},
    "R4 inscritos": {"organizador": 8, "aprobado": 10, "fuera": 9},
    "R5 anotacion": {"organizador": 13, "aprobado": 14, "fuera": 12},
    "R6 general": {"organizador": 13, "aprobado": 14, "fuera": 9},
}


@pytest.mark.parametrize("quien", ["organizador", "aprobado", "fuera"])
async def test_ninguna_lectura_crece(client: AsyncClient, privada, quien):
    """R10: el total de sentencias de cada lectura no sube del medido."""
    pasadas = {}
    for nombre, ruta in privada["rutas"].items():
        sentencias: list = []

        def _apunta(conn, cursor, statement, *args, apuntadas=sentencias):
            apuntadas.append(statement)

        set_auth_cookies(client, privada["quien"][quien]["cookies"])
        event.listen(Engine, "before_cursor_execute", _apunta)
        try:
            await client.get(ruta)
        finally:
            event.remove(Engine, "before_cursor_execute", _apunta)
        if len(sentencias) > TOPES[nombre][quien]:
            pasadas[nombre] = (len(sentencias), TOPES[nombre][quien])

    assert pasadas == {}, pasadas
