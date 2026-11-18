"""
El parámetro `page` de todas las listas, con tope (S-11, auditoría del 18 nov 2026).

Sin máximo, una página enorme es un OFFSET enorme que la base recorre entero. 1.000
páginas de hasta 100 elementos son 100.000 filas: muy por encima de cualquier lista
real. Lo vigila tests/unit/shared/infrastructure/http/test_tope_de_pagina.py en todas
las rutas.
"""

from typing import Any

from fastapi import Query

PAGINA_MAXIMA = 1000


def parametro_page() -> Any:
    """`page` de una lista: 1 por defecto, entre 1 y PAGINA_MAXIMA (si no, 422)."""
    return Query(1, ge=1, le=PAGINA_MAXIMA)
