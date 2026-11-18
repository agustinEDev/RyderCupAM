"""
Los logs no llevan el nombre completo de nadie (Q-BE-08, auditoría del 18 nov 2026).

Los correos se enmascaran, pero había 7 logs con `get_full_name()`. Se apunta el id del
usuario: sirve igual para seguir el caso y no es un dato personal a la vista. Vigila todo
`src/`: cualquier `logger.<nivel>(...)` (o `logging.<nivel>`) con un argumento que llame
a `get_full_name()`, o use `full_name` (atributo o variable), falla.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3] / "src"
NIVELES = {"debug", "info", "warning", "error", "exception", "critical", "log"}
NOMBRES = {"get_full_name", "full_name"}


def _llama_a_un_nombre(nodo: ast.AST) -> bool:
    return any(
        (isinstance(h, ast.Attribute) and h.attr in NOMBRES)
        or (isinstance(h, ast.Name) and h.id in NOMBRES)
        for h in ast.walk(nodo)
    )


def _logs_con_nombres() -> list[str]:
    hallados = []
    for fichero in RAIZ.rglob("*.py"):
        arbol = ast.parse(fichero.read_text(), filename=str(fichero))
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in NIVELES
                and isinstance(nodo.func.value, ast.Name)
                and nodo.func.value.id in {"logger", "logging", "log"}
                and any(
                    _llama_a_un_nombre(a) for a in [*nodo.args, *(k.value for k in nodo.keywords)]
                )
            ):
                hallados.append(f"{fichero.relative_to(RAIZ.parent)}:{nodo.lineno}")
    return hallados


def test_no_log_call_carries_a_full_name():
    """
    Given: Todo src/
    When: Se buscan llamadas al log con get_full_name() o full_name
    Then: No hay ninguna
    """
    assert _logs_con_nombres() == []
