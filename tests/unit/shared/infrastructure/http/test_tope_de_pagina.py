"""
Ninguna ruta acepta un número de página sin tope (S-11, auditoría del 18 nov 2026).

`page` era `Query(1, ge=1)` sin máximo: con `limit` ≤ 100, una página enorme es un OFFSET
enorme que la base recorre entero. Tope común: PAGINA_MAXIMA (1.000 páginas de hasta 100).
Vigila todas las rutas de la app, también las que se añadan.

  B3-1 page=1000           -> como hoy
  B3-2 page=1001           -> 422
  B3-3 sin page            -> la 1, como hoy
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.infrastructure.http.paginacion import OFFSET_MAXIMO, PAGINA_MAXIMA


def _parametros_page(app: FastAPI, nombre: str = "page") -> list[tuple[str, dict]]:
    esquema = app.openapi()
    encontrados = []
    for ruta, metodos in esquema["paths"].items():
        for metodo, operacion in metodos.items():
            for parametro in operacion.get("parameters", []):
                if parametro["name"] == nombre and parametro["in"] == "query":
                    encontrados.append((f"{metodo.upper()} {ruta}", parametro["schema"]))
    return encontrados


def test_every_page_parameter_of_the_app_has_the_shared_cap():
    """
    Given: Todas las rutas de la app
    When: Se mira su parámetro `page`
    Then: Todas tienen mínimo 1 y máximo PAGINA_MAXIMA (y hay alguna: no pasa en vacío)
    """
    import main

    parametros = _parametros_page(main.app)

    assert len(parametros) >= 5
    sin_tope = [r for r, s in parametros if s.get("maximum") != PAGINA_MAXIMA]
    assert sin_tope == []
    assert all(s.get("minimum") == 1 for _, s in parametros)
    # El tope aprobado, escrito aquí: si alguien cambia la constante, esto falla
    # (CodeRabbit: comparar con la constante se movería con ella)
    assert PAGINA_MAXIMA == 1000


@pytest.mark.parametrize(
    ("consulta", "codigo", "pagina"),
    [("?page=1000", 200, 1000), ("?page=1001", 422, None), ("", 200, 1)],
)
def test_b3_the_cap_is_enforced(consulta, codigo, pagina):
    """
    Given: Una ruta con el parámetro como las de la app
    When: Se pide una página
    Then: Hasta el tope responde; por encima, 422; sin página, la 1
    """
    from src.shared.infrastructure.http.paginacion import parametro_page

    app = FastAPI()

    @app.get("/lista")
    async def lista(page: int = parametro_page()):
        return {"page": page}

    respuesta = TestClient(app).get(f"/lista{consulta}")

    assert respuesta.status_code == codigo
    if pagina is not None:
        assert respuesta.json() == {"page": pagina}


def test_every_offset_parameter_of_the_app_has_the_shared_cap():
    """
    Given: Todas las rutas de la app
    When: Se mira su parámetro `offset` (el gemelo de `page`, revisión de la PR)
    Then: Todos tienen mínimo 0 y máximo OFFSET_MAXIMO
    """
    import main

    parametros = _parametros_page(main.app, "offset")

    assert len(parametros) >= 2
    assert [r for r, s in parametros if s.get("maximum") != OFFSET_MAXIMO] == []
    assert OFFSET_MAXIMO == 100_000
    assert all(s.get("minimum") == 0 for _, s in parametros)
