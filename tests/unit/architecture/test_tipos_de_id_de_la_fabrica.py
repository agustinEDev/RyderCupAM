"""
Los tipos de persistencia de ids y de país salen de la fábrica (20 nov 2026).

Había 38 escritos a mano, casi iguales, con cinco comportamientos distintos al
guardar: unos guardaban NULL sin avisar con un `uuid.UUID`, otros reventaban
con un texto. Ahora salen todos de `tipos_de_id.py` (`tipo_de_id` y
`tipo_de_codigo_de_pais`) y cada módulo declara el suyo con una línea. Este
test lee el código para que no vuelva a aparecer uno a mano: una clase que
hereda de `TypeDecorator` y se llama `...IdType`, `...IdDecorator` o
`CountryCode...`, o cuya columna es la de un id o un país (`CHAR(36)`,
`String(36)`, `VARCHAR`, `UUID`, `CHAR(2)`, `String(2)`, también con
`length=` o anotada).
"""

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3] / "src"
LA_FABRICA = RAIZ / "shared" / "infrastructure" / "persistence" / "sqlalchemy" / "tipos_de_id.py"

NOMBRE = re.compile(r"(Id(Type|Decorator)|^_?CountryCode\w*)$")
COLUMNA = re.compile(
    r"^(?:\w+\.)*(?:CHAR|String|VARCHAR)\((?:length=)?(?:36|2)\)$|^(?:\w+\.)*(?:UUID|Uuid)\b"
)


def _decoradores_a_mano(codigo: str) -> list[str]:
    """Las clases TypeDecorator con forma de tipo de id o de país."""
    encontrados = []
    for nodo in ast.walk(ast.parse(codigo)):
        if not isinstance(nodo, ast.ClassDef):
            continue
        if not any("TypeDecorator" in ast.unparse(b) for b in nodo.bases):
            continue
        impl = next(
            (
                ast.unparse(s.value)
                for s in nodo.body
                if (
                    isinstance(s, ast.Assign)
                    and any(getattr(t, "id", "") == "impl" for t in s.targets)
                )
                or (
                    isinstance(s, ast.AnnAssign)
                    and getattr(s.target, "id", "") == "impl"
                    and s.value
                )
            ),
            "",
        )
        if NOMBRE.search(nodo.name) or COLUMNA.search(impl):
            encontrados.append(f"{nodo.name} (línea {nodo.lineno})")
    return encontrados


def test_ningun_tipo_de_id_ni_de_pais_escrito_a_mano():
    """
    Given: Todo el código de src salvo la propia fábrica
    When: Se buscan clases TypeDecorator con forma de id o de país
    Then: No hay ninguna: se declaran con `tipo_de_id` / `tipo_de_codigo_de_pais`
    """
    hallazgos = [
        f"{ruta.relative_to(RAIZ)}: {clase}"
        for ruta in sorted(RAIZ.rglob("*.py"))
        if ruta != LA_FABRICA
        for clase in _decoradores_a_mano(ruta.read_text(encoding="utf-8"))
    ]
    assert hallazgos == []


def test_leer_src_encuentra_los_ficheros():
    """
    Given: la carpeta src
    When: se buscan ficheros
    Then: hay cientos y la fábrica existe (si no, el guardián no probaría nada)
    """
    assert len(list(RAIZ.rglob("*.py"))) > 500
    assert LA_FABRICA.exists()


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        ("class XIdDecorator(TypeDecorator):\n    impl = Text()", True),
        ("class XIdType(sqlalchemy.types.TypeDecorator[X]):\n    impl = Text()", True),
        ("class CountryCodeType(TypeDecorator):\n    impl = Text()", True),
        ("class Cualquiera(TypeDecorator):\n    impl = CHAR(36)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = String(2)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = UUID(as_uuid=True)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = postgresql.UUID(as_uuid=True)", True),
        ("class GenderDecorator(TypeDecorator):\n    impl = String(20)", False),
        ("class MatchResultJsonType(TypeDecorator):\n    impl = JSONB", False),
        ("class XIdDecorator(Base):\n    impl = CHAR(36)", False),
        ("XIdDecorator = tipo_de_id(XId)", False),
        ("class Cualquiera(TypeDecorator):\n    impl = CHAR(length=36)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = sa.String(length=2)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = VARCHAR(36)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = postgresql.UUID", True),
        ("class Cualquiera(TypeDecorator):\n    impl: Any = CHAR(36)", True),
        ("class Cualquiera(TypeDecorator):\n    impl = String(360)", False),
    ],
)
def test_detectar_cada_forma_da_lo_esperado(codigo, esperado):
    """
    Given: una forma de escribir un tipo (a mano o con la fábrica)
    When: se pasa al detector
    Then: la caza si es un tipo de id o de país a mano
    """
    assert bool(_decoradores_a_mano(codigo)) is esperado
