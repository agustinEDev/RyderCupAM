"""
La cabecera X-App-Mode pasa el CORS (BE #737).

La app instalada la manda en cada petición para que su dispositivo no se funda
con el de Safari. Si el CORS no la permitiera, el navegador rechazaría todas las
peticiones de la web a la API, que vive en otro subdominio.
"""

from src.config.cors_config import get_cors_config


def test_cors_allows_the_app_mode_header():
    """
    Given: La configuración CORS de la API
    When: Se miran las cabeceras permitidas
    Then: Incluye X-App-Mode, junto a X-CSRF-Token
    """
    cabeceras = get_cors_config()["allow_headers"]

    assert "X-App-Mode" in cabeceras
    assert "X-CSRF-Token" in cabeceras


def test_cors_no_longer_allows_the_authorization_header():
    """
    Given: La configuración CORS de la API (2.58.0: la sesión va solo en la cookie)
    When: Se miran las cabeceras permitidas
    Then: No incluye Authorization: la API ya no la lee y el front no la manda
    """
    cabeceras = [c.lower() for c in get_cors_config()["allow_headers"]]

    assert "authorization" not in cabeceras
