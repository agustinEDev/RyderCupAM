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
