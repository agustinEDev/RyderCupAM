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


def _es_un_logger(receptor: ast.AST) -> bool:
    """`logger`, `logging`, `log` y también `self._logger`, `self.logger`… (CodeRabbit)."""
    if isinstance(receptor, ast.Name):
        return receptor.id in {"logger", "logging", "log"}
    return isinstance(receptor, ast.Attribute) and "log" in receptor.attr.lower()


def _hallados_en(codigo: str, nombre: str) -> list[int]:
    lineas = []
    for nodo in ast.walk(ast.parse(codigo, filename=nombre)):
        if (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr in NIVELES
            and _es_un_logger(nodo.func.value)
            and any(_llama_a_un_nombre(a) for a in [*nodo.args, *(k.value for k in nodo.keywords)])
        ):
            lineas.append(nodo.lineno)
    return lineas


def _logs_con_nombres() -> list[str]:
    return [
        f"{fichero.relative_to(RAIZ.parent)}:{linea}"
        for fichero in RAIZ.rglob("*.py")
        for linea in _hallados_en(fichero.read_text(), str(fichero))
    ]


def test_no_log_call_carries_a_full_name():
    """
    Given: Todo src/
    When: Se buscan llamadas al log con get_full_name() o full_name
    Then: No hay ninguna
    """
    assert _logs_con_nombres() == []


def test_the_guard_sees_module_and_instance_loggers():
    """
    Given: El mismo log con el nombre, con `logger` y con `self._logger`
    When: Lo mira el vigilante
    Then: Ve los tres con el nombre; el del id, no
    """
    codigo = (
        "logger.warning('Player %s', user.get_full_name())\n"
        "self._logger.warning('Player %s', user.get_full_name())\n"
        "self._logger.info('Player %s', full_name)\n"
        "self._logger.warning('Player %s', user.id)\n"
    )

    assert _hallados_en(codigo, "prueba.py") == [1, 2, 3]
