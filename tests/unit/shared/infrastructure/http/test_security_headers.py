"""
La política de cabeceras de seguridad de la API, fijada al detalle.

Los tests de integración (test_security_headers.py) comprueban que ciertas
cabeceras EXISTEN; no verían una cabecera nueva que cambie el comportamiento.
Al pasar de secure 0.3 a 2 eso importaba: `Secure()` a secas no pone ninguna,
y los valores por defecto nuevos añaden CORP same-origin (bloquearía los
avatares que el frontend carga desde api.*), una CSP (rompería /docs) y quitan
Cache-Control: no-store. Aquí se fija exactamente lo que la API enviaba.
"""

from starlette.responses import Response

from src.shared.infrastructure.http.security_headers import apply_security_headers

POLITICA = {
    "strict-transport-security": "max-age=63072000; includesubdomains",
    "x-frame-options": "SAMEORIGIN",
    "x-xss-protection": "0",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer, strict-origin-when-cross-origin",
    "cache-control": "no-store",
}

NO_DEBEN_APARECER = [
    "cross-origin-resource-policy",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "content-security-policy",
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
        Then: lleva exactamente las seis cabeceras, con sus valores
        """
        response = Response("x")
        apply_security_headers(response)
        assert _cabeceras(response) == POLITICA

    def test_headers_that_would_change_behaviour_are_not_added(self):
        """
        Given: una respuesta
        When: se le aplica la política
        Then: no aparece ninguna cabecera que cambie el comportamiento (CORP, CSP...)
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
