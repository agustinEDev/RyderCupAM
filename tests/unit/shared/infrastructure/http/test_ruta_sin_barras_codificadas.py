"""
Una ruta con una barra codificada (`%2F`, `%5C`) se rechaza con 400 (FE-03, fase 4 del
plan a 9; probador de la FE #1098, 11 nov 2026).

Uvicorn decodifica la ruta antes de que Starlette enrute, así que `%2F` dentro de un id
se convertía en un separador: `GET /api/v1%2Fcountries` contestaba 200, y un id con `/`
añadía tramos y llegaba a otro endpoint. El front ya no los manda; esto lo cierra para
cualquier cliente.

| Caso | Petición                                              | Esperado              |
|------|-------------------------------------------------------|-----------------------|
| B1   | GET /api/v1%2Fcountries                               | 400 (antes 200)       |
| B2   | %2f en minúsculas                                     | 400                   |
| B3   | %5C y %5c                                             | 400                   |
| B4   | GET /health, y una ruta de la API que no existe       | 200 y 404, como antes |
| B5   | %2F en la búsqueda (?q=a%2Fb)                         | pasa                  |
| B6   | %20, %C3%A9 y %252F (doble) en la ruta                | pasan                 |
| B7   | el 400: formato de la API, sin repetir la ruta        | detail + error_code   |
| B8   | todos los métodos; /health; el 400 con las cabeceras  | 400 legible desde el  |
|      | de seguridad, CORS y correlation id. El preflight lo  | front                 |
|      | contesta CORS, como cualquier otro (Agustín, 11 nov)  |                       |
| B9   | lo que no es HTTP (el lifespan) pasa sin mirar        | pasa a la app         |
| B10  | un aviso en el log: método, IP y correlation id, sin  | warning               |
|      | la ruta                                               |                       |
| B11  | sin raw_path no se mira la ruta ya decodificada (daría | pasa a la app         |
|      | lo contrario: ni %2F real ni %252F legítimo)           |                       |
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

import main
from src.shared.infrastructure.http.ruta_sin_barras_codificadas import RutaSinBarrasCodificadas


@pytest.fixture
def cliente():
    """La app real, sin lanzar al test las excepciones del servidor."""
    return TestClient(main.app, raise_server_exceptions=False)


def _rechazada(respuesta) -> None:
    """El 400 de la ruta no válida, con el formato de la API y sin la ruta."""
    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "Ruta no válida", "error_code": "INVALID_PATH"}


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/v1%2Fcountries",  # B1
        "/api/v1%2fcountries",  # B2
        "/api/v1%5Ccountries",  # B3
        "/api/v1%5ccountries",  # B3
        "/api/v1/quick-matches/x%2Fshared",
        "/api/v1/countries/ES%2F..%2F..%2Fhealth",
    ],
)
def test_una_barra_codificada_en_la_ruta_da_400(cliente, ruta):
    """
    Given: La app
    When: GET a una ruta con una barra codificada
    Then: 400 INVALID_PATH, sin llegar a ningún endpoint
    """
    _rechazada(cliente.get(ruta))


def test_b4_la_ruta_normal_sigue_igual(cliente):
    """
    Given: La app (sin lifespan: nada que toque la BD)
    When: GET /health y GET a una ruta de la API que no existe
    Then: 200 y el 404 de siempre, no el 400 de la ruta
    """
    assert cliente.get("/health").status_code == 200
    assert cliente.get("/api/v1/no-existe").status_code == 404


def test_b5_en_la_busqueda_no_se_mira(cliente):
    """
    Given: La app
    When: GET /health?q=a%2Fb%5Cc
    Then: 200: la búsqueda no cambia la ruta
    """
    assert cliente.get("/health?q=a%2Fb%5Cc").status_code == 200


@pytest.mark.parametrize("tramo", ["a%20b", "Jos%C3%A9", "a%252Fb", "a%255Cb"])
def test_b6_otros_codificados_pasan(cliente, tramo):
    """
    Given: La app
    When: GET a una ruta con otros caracteres codificados (también %2F doble)
    Then: No es el 400 de la ruta: sigue a la app como antes
    """
    respuesta = cliente.get(f"/api/v1/no-existe/{tramo}")

    assert respuesta.status_code == 404


def test_b7_el_400_no_repite_la_ruta(cliente):
    """
    Given: La app
    When: GET a una ruta con %2F y un marcador
    Then: La respuesta no lleva el marcador
    """
    respuesta = cliente.get("/api/v1/marcador-secreto%2Fx")

    _rechazada(respuesta)
    assert "marcador-secreto" not in respuesta.text


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
def test_b8_todos_los_metodos(cliente, metodo):
    """
    Given: La app
    When: Cualquier método a una ruta con %2F
    Then: 400 (antes del CSRF y de la ruta)
    """
    respuesta = cliente.request(metodo, "/api/v1/competitions/x%2Fy")

    assert respuesta.status_code == 400


def test_b8_el_preflight_lo_contesta_cors(cliente):
    """
    Given: Un preflight de CORS desde el front
    When: OPTIONS a una ruta con %2F
    Then: Lo contesta CORS, como cualquier otro: 200 con sus cabeceras
    """
    respuesta = cliente.options(
        "/api/v1/competitions/x%2Fy",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"},
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_b8_el_400_se_lee_desde_el_front(cliente):
    """
    Given: El front, desde su origen
    When: GET a una ruta con %2F
    Then: El 400 lleva CORS (el navegador lo lee) y el correlation id
    """
    respuesta = cliente.get("/api/v1%2Fcountries", headers={"Origin": "http://localhost:5173"})

    _rechazada(respuesta)
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert respuesta.headers.get("x-correlation-id")


def test_b8_el_400_lleva_las_cabeceras_de_seguridad_y_health_sigue(cliente):
    """
    Given: La app
    When: GET a una ruta con %2F, y GET /health
    Then: El 400 lleva las cabeceras de seguridad; /health, 200
    """
    respuesta = cliente.get("/api/v1%2Fcountries")

    _rechazada(respuesta)
    assert "x-content-type-options" in respuesta.headers
    assert (
        respuesta.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    assert cliente.get("/health").status_code == 200


def test_b9_lo_que_no_es_http_pasa():
    """
    Given: El middleware suelto, sobre una app que apunta lo que le llega
    When: Un scope de lifespan, aunque traiga una ruta con %2F
    Then: Pasa a la app sin responder nada
    """
    llegan = []
    enviados = []

    async def app(scope, receive, send):
        llegan.append(scope["type"])

    async def send(mensaje):
        enviados.append(mensaje)

    async def receive():
        return {"type": "lifespan.startup"}

    asyncio.run(
        RutaSinBarrasCodificadas(app)({"type": "lifespan", "raw_path": b"/a%2Fb"}, receive, send)
    )

    assert llegan == ["lifespan"]
    assert enviados == []


def test_b10_deja_un_aviso_sin_la_ruta(cliente, caplog):
    """
    Given: La app
    When: DELETE a una ruta con %2F y un marcador
    Then: Un warning con el método y el correlation id, sin la ruta
    """
    with caplog.at_level(
        "WARNING", logger="src.shared.infrastructure.http.ruta_sin_barras_codificadas"
    ):
        respuesta = cliente.delete(
            "/api/v1/marcador-secreto%2Fx", headers={"X-Correlation-ID": "corr-1234"}
        )

    assert respuesta.status_code == 400
    avisos = [r for r in caplog.records if r.name.endswith("ruta_sin_barras_codificadas")]
    assert len(avisos) == 1
    assert avisos[0].levelname == "WARNING"
    assert "DELETE" in avisos[0].getMessage()
    assert "corr-1234" in avisos[0].getMessage()
    assert "marcador-secreto" not in avisos[0].getMessage()


@pytest.mark.parametrize("ruta", ["/a/b", "/a%2Fb"])
def test_b11_sin_raw_path_no_mira_la_ruta_decodificada(ruta):
    """
    Given: El middleware suelto y un servidor que no manda raw_path
    When: Una petición cuya ruta ya decodificada es /a/b o /a%2Fb (de un %252F legítimo)
    Then: Pasa a la app: lo decodificado no dice si había una barra codificada
    """
    llegan = []

    async def app(scope, receive, send):
        llegan.append(scope["path"])

    async def send(mensaje):
        raise AssertionError(mensaje)

    async def receive():
        return {"type": "http.request"}

    asyncio.run(
        RutaSinBarrasCodificadas(app)(
            {"type": "http", "method": "GET", "path": ruta, "headers": []}, receive, send
        )
    )

    assert llegan == [ruta]
