"""
El esquema OpenAPI, privado como /docs (F-11, auditoría OWASP del 9 nov 2026).

/docs y /redoc pedían HTTP Basic, pero /openapi.json, con el mapa entero de la API,
estaba abierto. Ahora pide las mismas credenciales, y las tres rutas tienen un límite
por red de las credenciales EQUIVOCADAS: antes estaban exentas de todo límite, y
probar contraseñas era gratis. Las buenas ni cuentan ni se frenan: sin la IP real, la
red es toda la app, y cualquiera dejaría al administrador sin documentación
(/code-review de la fase 2).

El job «API contract» del CI no pide nada por HTTP: genera el esquema importando la
app (`app.openapi()`), y eso sigue igual.
"""

import base64

import pytest
from fastapi.testclient import TestClient

import main
from src.config import rate_limit
from src.config.rate_limit import EXEMPT_FROM_DEFAULT_LIMIT, limiter

USUARIO = "docs-user"
CLAVE = "docs-pass-de-prueba"  # nosec B105 - test credential, not a real secret
RUTAS = ["/openapi.json", "/docs", "/redoc"]


def _basic(usuario: str, clave: str) -> dict[str, str]:
    """La cabecera Authorization de HTTP Basic."""
    return {"Authorization": "Basic " + base64.b64encode(f"{usuario}:{clave}".encode()).decode()}


@pytest.fixture
def cliente(monkeypatch):
    """La app real con las credenciales de la documentación configuradas."""
    monkeypatch.setattr(main.settings, "DOCS_USERNAME", USUARIO)
    monkeypatch.setattr(main.settings, "DOCS_PASSWORD", CLAVE)
    return TestClient(main.app)


@pytest.mark.parametrize("ruta", RUTAS)
def test_without_credentials_it_is_401(cliente, ruta):
    """
    Given: La app con la documentación protegida
    When: Se pide la ruta sin credenciales
    Then: 401 con WWW-Authenticate: Basic
    """
    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Basic"


@pytest.mark.parametrize("ruta", RUTAS)
def test_with_wrong_credentials_it_is_401(cliente, ruta):
    """
    Given: La app con la documentación protegida
    When: Se pide la ruta con una contraseña equivocada
    Then: 401
    """
    assert cliente.get(ruta, headers=_basic(USUARIO, "otra")).status_code == 401


def test_with_credentials_the_schema_is_served(cliente):
    """
    Given: La app con la documentación protegida
    When: Se pide /openapi.json con las credenciales
    Then: 200 con el mismo esquema que genera la app (el que compara el CI)
    """
    respuesta = cliente.get("/openapi.json", headers=_basic(USUARIO, CLAVE))

    assert respuesta.status_code == 200
    assert respuesta.json() == main.app.openapi()


@pytest.mark.parametrize("ruta", ["/docs", "/redoc"])
def test_with_credentials_the_docs_pages_load_the_private_schema(cliente, ruta):
    """
    Given: La app con la documentación protegida
    When: Se piden las páginas con las credenciales
    Then: 200, y cargan /openapi.json (el navegador le manda las mismas credenciales)
    """
    respuesta = cliente.get(ruta, headers=_basic(USUARIO, CLAVE))

    assert respuesta.status_code == 200
    assert "/openapi.json" in respuesta.text


def test_the_schema_generated_offline_is_unchanged():
    """
    Given: La app importada sin servidor (como el job «API contract» del CI)
    When: Se genera su esquema
    Then: Sale, y no incluye las rutas de la documentación
    """
    esquema = main.app.openapi()

    assert esquema["paths"]
    assert not {"/openapi.json", "/docs", "/redoc"} & set(esquema["paths"])


def test_the_docs_routes_are_exempt_from_the_default_limit():
    """
    Given: Las rutas de la documentación
    When: Se mira la lista de exentas del límite por defecto (por usuario)
    Then: Están las tres: su límite es el de los fallos de credenciales, por red
    """
    rutas = {r.path: r for r in main.app.routes if getattr(r, "path", None) in RUTAS}

    assert set(rutas) == set(RUTAS)
    for ruta in rutas.values():
        assert f"{ruta.endpoint.__module__}.{ruta.endpoint.__name__}" in EXEMPT_FROM_DEFAULT_LIMIT


@pytest.fixture
def limite_de_2(monkeypatch):
    """El límite de la documentación a 2 por minuto, con el limitador encendido."""
    monkeypatch.setattr(rate_limit, "DOCS_LIMIT", "2/minute")
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    yield
    limiter.reset()


def test_failed_attempts_hit_the_limit_and_get_429(cliente, limite_de_2):
    """
    Given: El límite de la documentación a 2 por minuto
    When: Se prueban 3 contraseñas equivocadas desde la misma red
    Then: 401, 401 y 429: cada fallo cuenta, y pasado el límite se frena
    """
    cabeceras = {**_basic(USUARIO, "mala"), "X-Test-Client-ID": "fuerza-bruta"}

    codigos = [cliente.get("/openapi.json", headers=cabeceras).status_code for _ in range(3)]

    assert codigos == [401, 401, 429]


def test_good_credentials_never_count(cliente, limite_de_2):
    """
    Given: El límite de la documentación a 2 por minuto
    When: El administrador abre la documentación 5 veces con sus credenciales
    Then: 200 las 5: un acierto ni cuenta ni se frena
    """
    cabeceras = {**_basic(USUARIO, CLAVE), "X-Test-Client-ID": "admin"}

    codigos = [cliente.get("/openapi.json", headers=cabeceras).status_code for _ in range(5)]

    assert codigos == [200] * 5


def test_an_exhausted_bucket_does_not_lock_out_the_admin(cliente, limite_de_2):
    """
    Given: El contador de una red agotado con contraseñas equivocadas (sin la IP real,
           en producción es toda la app: el cubo compartido)
    When: El administrador entra desde esa misma red con sus credenciales
    Then: 200: nadie puede dejarle sin documentación probando contraseñas
    """
    mala = {**_basic(USUARIO, "mala"), "X-Test-Client-ID": "cubo-compartido"}
    buena = {**_basic(USUARIO, CLAVE), "X-Test-Client-ID": "cubo-compartido"}
    for _ in range(3):
        cliente.get("/docs", headers=mala)

    assert cliente.get("/docs", headers=buena).status_code == 200


@pytest.fixture
def ip_real(monkeypatch):
    """La petición trae la IP real de quien llama, verificada por Cloudflare (ADR-041)."""
    monkeypatch.setattr(rate_limit, "cloudflare_client_ip", lambda _peticion: "203.0.113.5")


def test_with_the_real_ip_a_full_bucket_blocks_even_good_credentials(cliente, limite_de_2, ip_real):
    """
    Given: La IP real de quien llama (su propio contador) y el límite a 2 por minuto
    When: Prueba 2 contraseñas equivocadas y después las buenas
    Then: 401, 401 y 429: con su contador lleno se le frena ANTES de comparar, también
          con las buenas, y la fuerza bruta no puede seguir probando (CodeRabbit)
    """
    mala = {**_basic(USUARIO, "mala"), "X-Test-Client-ID": "atacante"}
    buena = {**_basic(USUARIO, CLAVE), "X-Test-Client-ID": "atacante"}

    codigos = [cliente.get("/openapi.json", headers=mala).status_code for _ in range(2)]
    codigos.append(cliente.get("/openapi.json", headers=buena).status_code)

    assert codigos == [401, 401, 429]


def test_with_the_real_ip_another_network_is_not_blocked(cliente, limite_de_2, ip_real):
    """
    Given: El contador de una IP real lleno
    When: Entra el administrador con sus credenciales desde otra red
    Then: 200: cada IP real tiene su propio contador
    """
    mala = {**_basic(USUARIO, "mala"), "X-Test-Client-ID": "atacante"}
    for _ in range(3):
        cliente.get("/docs", headers=mala)

    buena = {**_basic(USUARIO, CLAVE), "X-Test-Client-ID": "admin"}

    assert cliente.get("/docs", headers=buena).status_code == 200


def test_with_the_real_ip_good_credentials_still_do_not_count(cliente, limite_de_2, ip_real):
    """
    Given: La IP real y el límite a 2 por minuto
    When: El administrador abre la documentación 5 veces con sus credenciales
    Then: 200 las 5: los aciertos siguen sin contar
    """
    buena = {**_basic(USUARIO, CLAVE), "X-Test-Client-ID": "admin"}

    assert [cliente.get("/docs", headers=buena).status_code for _ in range(5)] == [200] * 5


def test_the_docs_limit_is_per_network():
    """
    Given: El límite de la documentación
    When: Se mira su valor
    Then: 20 por minuto: para una persona que abre la documentación sobra, y probar
          contraseñas deja de ser gratis
    """
    assert rate_limit.DOCS_LIMIT == "20/minute"
