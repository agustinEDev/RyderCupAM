"""
La composition root fija el tope de bcrypt desde el entorno (auditoría 9 nov 2026).

El ejecutor de bcrypt vive en la capa de aplicación y leía
`BCRYPT_MAX_CONCURRENCY` con `src.config.env` al importarse. Ahora se lo fija
`src.config.contrasenas`, la misma pieza que instala el hasher con sus rondas.
"""

from src.config.contrasenas import instala_el_hasher_de_contrasenas
from src.shared.application.concurrencia.bcrypt_executor import (
    DEFAULT_MAX_CONCURRENCY,
    configura_la_concurrencia_de_bcrypt,
    max_concurrency,
)


def test_instalar_el_hasher_fija_el_tope_del_entorno(monkeypatch):
    """
    Given: BCRYPT_MAX_CONCURRENCY=3 en el entorno
    When: la composition root instala lo de las contraseñas
    Then: el ejecutor de bcrypt queda con un tope de 3
    """
    monkeypatch.setenv("BCRYPT_MAX_CONCURRENCY", "3")
    try:
        instala_el_hasher_de_contrasenas()
        assert max_concurrency() == 3
    finally:
        configura_la_concurrencia_de_bcrypt(DEFAULT_MAX_CONCURRENCY)


def test_sin_variable_el_tope_es_el_de_siempre(monkeypatch):
    """
    Given: sin BCRYPT_MAX_CONCURRENCY en el entorno
    When: la composition root instala lo de las contraseñas
    Then: el tope es 2, el de siempre
    """
    monkeypatch.delenv("BCRYPT_MAX_CONCURRENCY", raising=False)
    configura_la_concurrencia_de_bcrypt(5)
    try:
        instala_el_hasher_de_contrasenas()
        assert max_concurrency() == DEFAULT_MAX_CONCURRENCY == 2
    finally:
        configura_la_concurrencia_de_bcrypt(DEFAULT_MAX_CONCURRENCY)
