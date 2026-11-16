"""
Las páginas de /docs y /redoc, con sus scripts fijados e íntegros (P-02, auditoría del
16 nov 2026).

Antes cargaban `swagger-ui-dist@5` y `redoc@2` de jsDelivr: versión flotante, sin SRI y
sin CSP. Una versión maliciosa de cualquiera de los dos (o un jsDelivr comprometido) se
habría ejecutado en api.rydercupfriends.com con la sesión del administrador. Ahora cada
recurso del CDN va con versión exacta, `integrity` y `crossorigin`, y la página lleva una
CSP que solo deja ejecutar esos ficheros concretos y el script de arranque de Swagger.
"""

import base64
import hashlib
import re
from html.parser import HTMLParser

import pytest

from src.shared.infrastructure.http.paginas_de_la_documentacion import (
    CSP_DE_LA_DOCUMENTACION,
    pagina_de_redoc,
    pagina_de_swagger,
)

CDN = "https://cdn.jsdelivr.net/npm/"
VERSION_EXACTA = re.compile(r"^https://cdn\.jsdelivr\.net/npm/[a-z-]+@\d+\.\d+\.\d+/")
SRI = re.compile(r"^sha384-[A-Za-z0-9+/]{64}$")


class _Recursos(HTMLParser):
    """Los <script> y <link rel=stylesheet> de una página, con sus atributos."""

    def __init__(self) -> None:
        super().__init__()
        self.externos: list[dict[str, str | None]] = []
        self.en_linea: list[str] = []
        self._dentro_de_script = False

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "script":
            if atributos.get("src"):
                self.externos.append(atributos | {"_url": atributos["src"]})
            else:
                self._dentro_de_script = True
                self.en_linea.append("")
        if tag == "link" and atributos.get("rel") == "stylesheet":
            self.externos.append(atributos | {"_url": atributos["href"]})

    def handle_endtag(self, tag):
        if tag == "script":
            self._dentro_de_script = False

    def handle_data(self, data):
        if self._dentro_de_script:
            self.en_linea[-1] += data


def _recursos(pagina) -> _Recursos:
    recursos = _Recursos()
    recursos.feed(pagina.body.decode())
    return recursos


def _directivas() -> dict[str, list[str]]:
    return {
        partes[0]: partes[1:]
        for partes in (d.split() for d in CSP_DE_LA_DOCUMENTACION.split(";") if d.strip())
    }


PAGINAS = [
    pytest.param(pagina_de_swagger, id="swagger"),
    pytest.param(pagina_de_redoc, id="redoc"),
]


@pytest.mark.parametrize("pagina", PAGINAS)
def test_every_cdn_resource_has_an_exact_version_and_sri(pagina):
    """
    Given: la página de la documentación
    When: se mira cada script y hoja de estilos del CDN
    Then: lleva versión exacta (x.y.z), integrity sha384 y crossorigin=anonymous
    """
    del_cdn = [r for r in _recursos(pagina("/openapi.json")).externos if r["_url"].startswith(CDN)]

    assert del_cdn, "La página no carga nada del CDN: la expresión no casa"
    for recurso in del_cdn:
        assert VERSION_EXACTA.match(recurso["_url"]), recurso["_url"]
        assert SRI.match(recurso.get("integrity") or ""), recurso
        assert recurso.get("crossorigin") == "anonymous", recurso


@pytest.mark.parametrize("pagina", PAGINAS)
def test_the_csp_allows_exactly_the_scripts_of_the_page(pagina):
    """
    Given: la página y la CSP de la documentación
    When: se compara cada script de la página con script-src
    Then: cada script externo está en script-src por su URL completa, y cada script en
          línea por su hash sha256
    """
    recursos = _recursos(pagina("/openapi.json"))
    script_src = _directivas()["script-src"]

    for recurso in recursos.externos:
        if recurso.get("src"):
            assert recurso["src"] in script_src, recurso["src"]
    for script in recursos.en_linea:
        huella = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        assert f"'sha256-{huella}'" in script_src, "Script en línea sin su hash en la CSP"


def test_the_csp_is_strict_with_scripts():
    """
    Given: la CSP de la documentación
    When: se leen sus directivas
    Then: nada por defecto, sin scripts en línea sin hash ni hosts enteros, y nadie puede
          enmarcar la página
    """
    directivas = _directivas()

    assert directivas["default-src"] == ["'none'"]
    assert directivas["frame-ancestors"] == ["'none'"]
    assert directivas["object-src"] == ["'none'"]
    assert directivas["base-uri"] == ["'none'"]
    assert "'unsafe-inline'" not in directivas["script-src"]
    for fuente in directivas["script-src"]:
        assert fuente.startswith("'sha256-") or VERSION_EXACTA.match(fuente), fuente


def test_the_openapi_url_is_escaped_in_the_swagger_page():
    """
    Given: una URL del esquema con comillas y etiquetas
    When: se genera la página de Swagger
    Then: no rompe el script de arranque (va como JSON escapado)
    """
    cuerpo = pagina_de_swagger("/x'</script><script>alert(1)//").body.decode()

    assert "</script><script>alert(1)" not in cuerpo
