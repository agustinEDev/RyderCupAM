"""
La política de cabeceras de seguridad de la API, fijada al detalle.

Los tests de integración (test_security_headers.py) comprueban que ciertas
cabeceras EXISTEN; no verían una cabecera nueva que cambie el comportamiento.
Al pasar de secure 0.3 a 2 eso importaba: `Secure()` a secas no pone ninguna,
y los valores por defecto nuevos añaden CORP same-origin (bloquearía los
avatares que el frontend carga desde api.*), una CSP (rompería /docs) y quitan
Cache-Control: no-store. Aquí se fija exactamente lo que la API enviaba.

Desde F-15 (auditoría OWASP del 9 nov 2026) la API manda además una CSP que no deja
cargar nada ni enmarcarla, salvo en /docs y /redoc, que cargan sus scripts.
"""

import pytest
from starlette.responses import Response

from src.shared.infrastructure.http.security_headers import apply_security_headers

POLITICA = {
    "strict-transport-security": "max-age=63072000; includesubdomains",
    "x-frame-options": "SAMEORIGIN",
    "x-xss-protection": "0",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer, strict-origin-when-cross-origin",
    "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}

NO_DEBEN_APARECER = [
    "cross-origin-resource-policy",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "permissions-policy",
    "server",
]


def _cabeceras(response: Response) -> dict[str, str]:
    cabeceras = {k: v for k, v in response.headers.items() if k != "content-length"}
    # Las directivas de HSTS no distinguen mayúsculas (RFC 6797 §6.1):
    # secure 0.3 escribía includeSubdomains y secure 2 includeSubDomains
    if "strict-transport-security" in cabeceras:
        cabeceras["strict-transport-security"] = cabeceras["strict-transport-security"].lower()
    return cabeceras


class TestSecurityHeaders:
    def test_a_plain_response_gets_exactly_the_policy(self):
        """
        Given: una respuesta sin cabeceras propias
        When: se le aplica la política
        Then: lleva exactamente las siete cabeceras, con sus valores
        """
        response = Response("x")
        apply_security_headers(response)
        assert _cabeceras(response) == POLITICA

    def test_headers_that_would_change_behaviour_are_not_added(self):
        """
        Given: una respuesta
        When: se le aplica la política
        Then: no aparece ninguna cabecera que cambie el comportamiento (CORP, COOP...)
        """
        response = Response("x")
        apply_security_headers(response)
        presentes = [h for h in NO_DEBEN_APARECER if h in response.headers]
        assert presentes == []

    def test_a_route_cache_control_is_kept(self):
        """
        Given: una ruta que fija su propio Cache-Control (imágenes de avatar)
        When: se aplica la política
        Then: se respeta el de la ruta, no se pisa con no-store
        """
        response = Response("x", headers={"Cache-Control": "public, max-age=31536000, immutable"})
        apply_security_headers(response)
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"

    def test_without_route_cache_control_it_is_no_store(self):
        """
        Given: una ruta que no fija Cache-Control
        When: se aplica la política
        Then: no-store, para que las respuestas con datos de sesión no se cacheen
        """
        response = Response("x")
        apply_security_headers(response)
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.parametrize("ruta", ["/docs", "/redoc", "/docs/", "/redoc/"])
    def test_the_docs_pages_get_no_csp(self, ruta):
        """
        Given: una respuesta de las páginas de la documentación
        When: se aplica la política con su ruta
        Then: lleva todas las cabeceras menos la CSP, que rompería sus scripts
        """
        response = Response("x")
        apply_security_headers(response, ruta)
        esperadas = {k: v for k, v in POLITICA.items() if k != "content-security-policy"}
        assert _cabeceras(response) == esperadas

    @pytest.mark.parametrize("ruta", ["/openapi.json", "/docs/oauth2-redirect", "/api/v1/docs"])
    def test_other_routes_get_the_csp(self, ruta):
        """
        Given: otra ruta, aunque se parezca (el esquema, una subruta)
        When: se aplica la política con su ruta
        Then: lleva la CSP: la excepción es exacta
        """
        response = Response("x")
        apply_security_headers(response, ruta)
        assert response.headers["content-security-policy"] == POLITICA["content-security-policy"]
