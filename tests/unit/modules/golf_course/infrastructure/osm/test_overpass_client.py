"""
Tests del cliente de Overpass, la API de lectura de OpenStreetMap (BE #532).

Sin red: `respx` hace de Overpass. Lo que se protege es que una caída o un
límite de uso de Overpass llegue como «OSM no disponible», nunca como un 500, y
que la respuesta se traduzca a datos propios sin arrastrar lo que no se entiende.
"""

import httpx
import pytest
import respx

from src.modules.golf_course.application.ports.osm_hole_map_source import OsmUnavailableError
from src.modules.golf_course.infrastructure.osm.overpass_client import (
    DEFAULT_OVERPASS_URL,
    OverpassClient,
)

LAT, LON = 36.2858, -5.3247


def _geom(*pares):
    return [{"lat": lat, "lon": lon} for lat, lon in pares]


RESPUESTA = {
    "elements": [
        {
            "type": "way",
            "id": 237391513,
            "tags": {"leisure": "golf_course", "name": "Club de Golf Valderrama"},
            "geometry": _geom((36.28, -5.34), (36.29, -5.34), (36.29, -5.32), (36.28, -5.34)),
        },
        {
            "type": "relation",
            "id": 99,
            "tags": {"leisure": "golf_course", "type": "multipolygon"},
            "members": [
                {"type": "way", "ref": 1, "role": "outer", "geometry": _geom((1, 1), (1, 2))},
                {
                    "type": "way",
                    "ref": 2,
                    "role": "outer",
                    "geometry": _geom((1, 2), (2, 2), (1, 1)),
                },
                {
                    "type": "way",
                    "ref": 3,
                    "role": "inner",
                    "geometry": _geom((1.2, 1.5), (1.3, 1.5), (1.2, 1.5)),
                },
                {"type": "node", "ref": 4, "role": "label"},
            ],
        },
        {
            "type": "way",
            "id": 10,
            "tags": {"golf": "hole", "ref": "1", "par": "4", "handicap": "11"},
            "geometry": _geom((36.281, -5.33), (36.284, -5.33)),
        },
        {
            "type": "way",
            "id": 20,
            "tags": {"golf": "green"},
            "geometry": _geom(
                (36.2841, -5.3301), (36.2841, -5.3299), (36.2839, -5.3299), (36.2841, -5.3301)
            ),
        },
        {"type": "way", "id": 30, "tags": {"golf": "bunker"}, "geometry": _geom((1, 1), (1, 2))},
        {"type": "way", "id": 31, "tags": {"golf": "hole", "ref": "2"}},
        {"type": "node", "id": 40, "lat": 36.28, "lon": -5.33, "tags": {"golf": "pin"}},
    ]
}


def _client(sleeps=None):
    async def sleep(seconds):
        if sleeps is not None:
            sleeps.append(seconds)

    return OverpassClient(sleep=sleep)


# ============================================================================
# O1-O2 — Consulta y traducción
# ============================================================================


@pytest.mark.asyncio
@respx.mock
async def test_o1_one_query_around_our_point_with_geometry():
    """
    GIVEN: Una coordenada de campo
    WHEN: Se pide la zona a Overpass
    THEN: Va una sola consulta POST, con radio de 2,5 km alrededor del punto y
         los contornos (vías y relaciones), hoyos y greens, con geometría
    """
    route = respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(200, json=RESPUESTA))

    await _client().fetch_area(LAT, LON)

    assert route.call_count == 1
    query = httpx.QueryParams(route.calls[0].request.content.decode())["data"]
    around = f"around:2500,{LAT},{LON}"
    assert f'way["leisure"="golf_course"]({around})' in query
    assert f'relation["leisure"="golf_course"]({around})' in query
    assert f'way["golf"="hole"]({around})' in query
    assert f'way["golf"="green"]({around})' in query
    assert "out tags geom" in query
    assert "[out:json]" in query


@pytest.mark.asyncio
@respx.mock
async def test_o2_response_becomes_own_data():
    """
    GIVEN: Una respuesta con contorno (vía y relación), hoyo, green y cosas que no se usan
    WHEN: Se traduce
    THEN: Salen contornos, hoyos y greens con sus puntos (lat, lon) y etiquetas;
         lo demás (bunkers, nodos, vías sin geometría) se ignora
    """
    respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(200, json=RESPUESTA))

    area = await _client().fetch_area(LAT, LON)

    (way,) = area.course_ways
    assert way.id == 237391513
    assert way.points[0] == (36.28, -5.34)
    (relation,) = area.course_relations
    assert relation.id == 99
    assert relation.outer == (((1, 1), (1, 2)), ((1, 2), (2, 2), (1, 1)))
    assert relation.inner == (((1.2, 1.5), (1.3, 1.5), (1.2, 1.5)),)
    (hole,) = area.holes
    assert hole.id == 10
    assert hole.tags["ref"] == "1"
    assert hole.tags["handicap"] == "11"
    assert len(hole.points) == 2
    (green,) = area.greens
    assert green.id == 20
    assert len(green.points) == 4


@pytest.mark.asyncio
@respx.mock
async def test_o2_empty_area():
    """
    GIVEN: Overpass no encuentra nada
    WHEN: Se traduce
    THEN: Una zona vacía, no un error
    """
    respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))

    area = await _client().fetch_area(LAT, LON)

    assert (area.course_ways, area.course_relations, area.holes, area.greens) == ((), (), (), ())


# ============================================================================
# O3-O5 — Fallos de Overpass
# ============================================================================


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_o3_busy_overpass_is_retried(status):
    """
    GIVEN: Overpass responde 429/502/503/504 (límite o pasarela cargada) y luego bien
    WHEN: Se pide la zona
    THEN: Se reintenta tras esperar y se devuelve la respuesta buena
    """
    route = respx.post(DEFAULT_OVERPASS_URL).mock(
        side_effect=[httpx.Response(status), httpx.Response(200, json={"elements": []})]
    )
    sleeps = []

    await _client(sleeps).fetch_area(LAT, LON)

    assert route.call_count == 2
    assert len(sleeps) == 1


@pytest.mark.asyncio
@respx.mock
async def test_o3_retries_twice_with_growing_waits_then_gives_up():
    """
    GIVEN: Overpass responde 504 siempre
    WHEN: Se pide la zona
    THEN: Tres intentos (dos reintentos), esperas crecientes, y «OSM no disponible»
    """
    route = respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(504))
    sleeps = []

    with pytest.raises(OsmUnavailableError):
        await _client(sleeps).fetch_area(LAT, LON)

    assert route.call_count == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0] > 0


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status", [400, 500])
async def test_o3_other_error_status_is_not_retried(status):
    """
    GIVEN: Overpass responde 400 (consulta mala) o 500
    WHEN: Se pide la zona
    THEN: Sin reintentos: «OSM no disponible» al primer intento
    """
    route = respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(status))

    with pytest.raises(OsmUnavailableError):
        await _client().fetch_area(LAT, LON)

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "error", [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), httpx.ConnectError("c")]
)
async def test_o4_network_failure_is_osm_unavailable(error):
    """
    GIVEN: Se agota el tiempo o falla la red siempre
    WHEN: Se pide la zona
    THEN: Tres intentos (es el síntoma más común de un Overpass saturado) y
         «OSM no disponible»
    """
    route = respx.post(DEFAULT_OVERPASS_URL).mock(side_effect=error)
    sleeps = []

    with pytest.raises(OsmUnavailableError):
        await _client(sleeps).fetch_area(LAT, LON)

    assert route.call_count == 3
    assert len(sleeps) == 2


@pytest.mark.asyncio
@respx.mock
async def test_o4_timeout_then_answer_is_retried():
    """
    GIVEN: Una consulta que agota el tiempo y luego responde
    WHEN: Se pide la zona
    THEN: Se reintenta y se devuelve la respuesta
    """
    respx.post(DEFAULT_OVERPASS_URL).mock(
        side_effect=[httpx.ReadTimeout("t"), httpx.Response(200, json={"elements": []})]
    )

    area = await _client().fetch_area(LAT, LON)

    assert area.holes == ()


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>busy</html>"),
        httpx.Response(200, json={"remark": "runtime error"}),
        httpx.Response(200, json=["no", "es", "un", "objeto"]),
    ],
    ids=["no-json", "sin-elements", "no-objeto"],
)
async def test_o5_unreadable_response_is_osm_unavailable(response):
    """
    GIVEN: Una respuesta 200 que no es el JSON esperado
    WHEN: Se pide la zona
    THEN: «OSM no disponible»
    """
    respx.post(DEFAULT_OVERPASS_URL).mock(return_value=response)

    with pytest.raises(OsmUnavailableError):
        await _client().fetch_area(LAT, LON)


@pytest.mark.asyncio
@respx.mock
async def test_o6_sends_its_own_user_agent():
    """
    GIVEN: Cualquier consulta
    WHEN: Se envía
    THEN: Lleva un User-Agent que identifica a la app, como pide Overpass
    """
    route = respx.post(DEFAULT_OVERPASS_URL).mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    await _client().fetch_area(LAT, LON)

    assert "RyderCupFriends" in route.calls[0].request.headers["user-agent"]


# ============================================================================
# Revisión — respuestas raras de Overpass
# ============================================================================


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "remark",
    [
        'runtime error: Query timed out in "query" at line 1 after 61 seconds.',
        "runtime error: Query run out of memory using about 2048 MB of RAM.",
    ],
)
async def test_o5_runtime_error_remark_is_osm_unavailable(remark):
    """
    GIVEN: Un 200 con «runtime error» en `remark` (Overpass cortó la consulta) y
           una lista de elementos a medias
    WHEN: Se pide la zona
    THEN: «OSM no disponible»: lo que llegó no está completo
    """
    body = {"remark": remark, "elements": RESPUESTA["elements"][:1]}
    respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(200, json=body))

    with pytest.raises(OsmUnavailableError):
        await _client().fetch_area(LAT, LON)


@pytest.mark.asyncio
@respx.mock
async def test_o2_malformed_elements_are_skipped():
    """
    GIVEN: Elementos sin id, con coordenadas que no son números o NaN, o con
           etiquetas que no son un diccionario, junto a un hoyo bueno
    WHEN: Se traduce
    THEN: Se saltan los malos y se queda el bueno, sin reventar
    """
    bueno = RESPUESTA["elements"][2]
    malos = [
        {"type": "way", "tags": {"golf": "hole", "ref": "3"}, "geometry": _geom((1, 1), (1, 2))},
        {
            "type": "way",
            "id": 50,
            "tags": {"golf": "hole"},
            "geometry": [{"lat": "x", "lon": 1}, {"lat": 1, "lon": 2}],
        },
        {
            "type": "way",
            "id": 51,
            "tags": {"golf": "hole"},
            "geometry": [{"lat": "nan", "lon": 1}, {"lat": 1, "lon": 2}],
        },
        {"type": "way", "id": 52, "tags": ["golf", "hole"], "geometry": _geom((1, 1), (1, 2))},
    ]
    respx.post(DEFAULT_OVERPASS_URL).mock(
        return_value=httpx.Response(200, json={"elements": [*malos, bueno]})
    )

    area = await _client().fetch_area(LAT, LON)

    assert [h.id for h in area.holes] == [10]


@pytest.mark.asyncio
@respx.mock
async def test_o2_relation_member_without_role_is_outer():
    """
    GIVEN: Una relación cuyos miembros no tienen rol (multipolígonos antiguos)
    WHEN: Se traduce
    THEN: Se toman como anillo exterior
    """
    relacion = {
        "type": "relation",
        "id": 8,
        "tags": {"leisure": "golf_course"},
        "members": [
            {"type": "way", "ref": 1, "role": "", "geometry": _geom((1, 1), (1, 2), (2, 2), (1, 1))}
        ],
    }
    respx.post(DEFAULT_OVERPASS_URL).mock(
        return_value=httpx.Response(200, json={"elements": [relacion]})
    )

    area = await _client().fetch_area(LAT, LON)

    assert area.course_relations[0].outer == (((1, 1), (1, 2), (2, 2), (1, 1)),)


@pytest.mark.asyncio
@respx.mock
async def test_o3_retry_after_is_respected():
    """
    GIVEN: Un 429 que pide esperar 45 s (Retry-After)
    WHEN: Se pide la zona
    THEN: Se espera lo que pide, si es más que la espera propia
    """
    respx.post(DEFAULT_OVERPASS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "45"}),
            httpx.Response(200, json={"elements": []}),
        ]
    )
    sleeps = []

    await _client(sleeps).fetch_area(LAT, LON)

    assert sleeps == [45.0]


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("header", ["3", "tomorrow", "100000"], ids=["menor", "ilegible", "enorme"])
async def test_o3_retry_after_never_shortens_nor_explodes_the_wait(header):
    """
    GIVEN: Un Retry-After menor que la espera propia, ilegible o desmesurado
    WHEN: Se reintenta
    THEN: Se espera al menos lo propio y como mucho 2 minutos
    """
    respx.post(DEFAULT_OVERPASS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": header}),
            httpx.Response(200, json={"elements": []}),
        ]
    )
    sleeps = []

    await _client(sleeps).fetch_area(LAT, LON)

    assert 10.0 <= sleeps[0] <= 120.0


@pytest.mark.asyncio
@respx.mock
async def test_o7_one_connection_for_the_whole_run(monkeypatch):
    """
    GIVEN: Un cliente que pide dos zonas
    WHEN: Se cierra al terminar
    THEN: Ha usado una sola conexión (un solo httpx.AsyncClient) y queda cerrada
    """
    from src.modules.golf_course.infrastructure.osm import overpass_client

    creados = []
    original = overpass_client.httpx.AsyncClient

    def contar(*args, **kwargs):
        creados.append(original(*args, **kwargs))
        return creados[-1]

    monkeypatch.setattr(overpass_client.httpx, "AsyncClient", contar)
    respx.post(DEFAULT_OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
    client = _client()

    await client.fetch_area(LAT, LON)
    await client.fetch_area(LAT, LON)
    await client.aclose()

    assert len(creados) == 1
    assert creados[0].is_closed
