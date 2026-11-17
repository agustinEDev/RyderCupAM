"""
Solo `instante_utc` lee la hora (re-auditoría F-02, 17 nov 2026).

`datetime.now()` sin zona da la hora LOCAL de la máquina, y ruff solo la caza cuando se
llama (DTZ005). Pasada sin llamar, como reloj por defecto (`reloj=datetime.now`), se colaba:
en una máquina fuera de UTC chocaba con las fechas, que se guardan en UTC. Los relojes son
los de `src/shared/domain/services/instante_utc.py`, el único módulo que lee la hora como
`datetime`. Se mira el código, no el texto: los comentarios y docstrings no cuentan, y un
import con alias (`from datetime import datetime as dt`) sí.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3] / "src"
EL_RELOJ = RAIZ / "shared" / "domain" / "services" / "instante_utc.py"


def _lecturas_del_reloj(arbol: ast.AST) -> list[int]:
    """Las líneas con `datetime.now` o `datetime.utcnow`, llamados o no, con alias o sin él."""
    clase = {"datetime"}  # nombres que valen la clase datetime
    modulo = {"datetime"}  # nombres que valen el módulo datetime
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "datetime":
            clase |= {a.asname or a.name for a in nodo.names if a.name == "datetime"}
        elif isinstance(nodo, ast.Import):
            modulo |= {a.asname or a.name for a in nodo.names if a.name == "datetime"}
    lineas = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Attribute) and nodo.attr in ("now", "utcnow")):
            continue
        valor = nodo.value
        if (isinstance(valor, ast.Name) and valor.id in clase) or (
            isinstance(valor, ast.Attribute)
            and valor.attr == "datetime"
            and isinstance(valor.value, ast.Name)
            and valor.value.id in modulo
        ):
            lineas.append(nodo.lineno)
    return lineas


def test_solo_instante_utc_lee_la_hora():
    """
    Given: Todo el código de src
    When: Se busca cualquier `datetime.now` (con zona o sin ella) o `datetime.utcnow`,
          llamado o no, también con alias
    Then: Solo aparece en instante_utc
    """
    encontrados = [
        f"{fichero.relative_to(RAIZ.parent)}:{linea}"
        for fichero in sorted(RAIZ.rglob("*.py"))
        if fichero != EL_RELOJ
        for linea in _lecturas_del_reloj(ast.parse(fichero.read_text(encoding="utf-8")))
    ]

    assert encontrados == [], "Lectura del reloj fuera de instante_utc:\n" + "\n".join(encontrados)


def test_la_busqueda_caza_alias_y_relojes_sin_llamar():
    """
    Given: Código con un alias, un reloj sin llamar y una mención en un docstring
    When: Se busca
    Then: Caza los dos primeros y no la mención
    """
    codigo = (
        "from datetime import datetime as dt\n"
        "import datetime as d\n"
        '"""no usar datetime.now"""\n'
        "def f(reloj=dt.now):\n"
        "    return d.datetime.utcnow()\n"
    )

    assert _lecturas_del_reloj(ast.parse(codigo)) == [4, 5]
