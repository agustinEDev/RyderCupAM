"""
Los parámetros `page` y `offset` de todas las listas, con tope (S-11, auditoría del 18 nov
2026; `offset`, en la revisión de la misma PR).

Sin máximo, una página enorme es un OFFSET enorme que la base recorre entero. 1.000
páginas de hasta 100 elementos son 100.000 filas: muy por encima de cualquier lista
real. Lo vigila tests/unit/shared/infrastructure/http/test_tope_de_pagina.py en todas
las rutas.
"""

from typing import Any

from fastapi import Query

PAGINA_MAXIMA = 1000
# El mismo alcance que PAGINA_MAXIMA páginas de 100: 100.000 elementos saltados como mucho
OFFSET_MAXIMO = PAGINA_MAXIMA * 100


def parametro_page() -> Any:
    """`page` de una lista: 1 por defecto, entre 1 y PAGINA_MAXIMA (si no, 422)."""
    return Query(1, ge=1, le=PAGINA_MAXIMA)


def parametro_offset(description: str | None = None) -> Any:
    """`offset` de una lista: 0 por defecto, entre 0 y OFFSET_MAXIMO (si no, 422)."""
    return Query(0, ge=0, le=OFFSET_MAXIMO, description=description)
