"""
El dominio de usuarios sin ciclos de importación (hallazgo B10 de la auditoría, fase 5).

El objeto de valor `Password` importaba el puerto del hasher desde `domain/services`, y la
entidad `TermsAcceptance` la versión de los Términos también desde ahí, mientras los servicios
importan entidades y objetos de valor: tres ciclos entre subpaquetes. El puerto vive ahora en
`domain/ports` y las reglas de los Términos en `domain/value_objects` (U1, U4); un contrato de
import-linter fija el orden de las capas (U2).
"""

import importlib
import itertools

import grimp
import pytest

USUARIOS = "src.modules.user"


def test_u1_ningun_par_de_subpaquetes_de_usuarios_se_importa_en_ciclo():
    """Given el grafo de importaciones, When se cruzan los subpaquetes de user, Then ningún par está en ciclo."""
    # Sin caché: con ella, un cambio hecho en el mismo segundo puede leerse con el grafo viejo
    grafo = grimp.build_graph("src", include_external_packages=False, cache_dir=None)
    paquetes = sorted(
        {
            ".".join(m.split(".")[:5])
            for m in grafo.modules
            if m.startswith(USUARIOS + ".") and len(m.split(".")) >= 5
        }
    )
    ciclos = [
        (a, b)
        for a, b in itertools.combinations(paquetes, 2)
        if grafo.find_shortest_chain(importer=a, imported=b, as_packages=True)
        and grafo.find_shortest_chain(importer=b, imported=a, as_packages=True)
    ]
    assert ciclos == []


@pytest.mark.parametrize(
    "ruta_vieja",
    [
        "src.modules.user.domain.services.password_hasher",
        "src.modules.user.domain.services.terms_of_service",
    ],
)
def test_u4_las_rutas_viejas_no_existen(ruta_vieja):
    """Given la ruta de antes, When se importa, Then falla: nadie puede parchear una copia muerta."""
    with pytest.raises(ImportError):
        importlib.import_module(ruta_vieja)
