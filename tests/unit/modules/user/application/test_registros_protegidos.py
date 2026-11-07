"""
Ningún registro del log de seguridad puede cambiar una respuesta (#750 punto 2, «everywhere»).

Guardián del código: en los casos de uso, toda llamada `.log_*(...)` (con cualquier receptor) va
dentro de `registra_sin_romper(..., lambda: ...)` o de un `try` que captura `Exception` sin
volver a lanzar. Así
un registro nuevo sin proteger hace fallar este test (el del login bueno se escapó así).
"""

import ast
from pathlib import Path

CASOS_DE_USO = sorted(Path("src/modules").glob("*/application/use_cases/*.py"))


def _es_un_registro(nodo: ast.AST) -> bool:
    if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)):
        return False
    # Cualquier receptor: con un alias del log también cuenta (revisor de seguridad)
    return nodo.func.attr.startswith("log_")


def _sin_proteger(fichero: Path) -> list[str]:
    arbol = ast.parse(fichero.read_text())
    padres: dict[ast.AST, ast.AST] = {}
    for padre in ast.walk(arbol):
        for hijo in ast.iter_child_nodes(padre):
            padres[hijo] = padre

    def protegido(nodo: ast.AST) -> bool:
        actual = nodo
        while actual in padres:
            padre = padres[actual]
            if isinstance(padre, ast.Lambda):
                llamada = padres.get(padre)
                if (
                    isinstance(llamada, ast.Call)
                    and isinstance(llamada.func, ast.Name)
                    and llamada.func.id == "registra_sin_romper"
                ):
                    return True
            if isinstance(padre, ast.Try) and actual in padre.body:
                for manejador in padre.handlers:
                    tipo = manejador.type
                    # Un manejador que vuelve a lanzar no protege nada
                    relanza = any(isinstance(n, ast.Raise) for n in ast.walk(manejador))
                    if isinstance(tipo, ast.Name) and tipo.id == "Exception" and not relanza:
                        return True
            actual = padre
        return False

    return [
        f"{fichero}:{n.lineno} {n.func.attr}"
        for n in ast.walk(arbol)
        if _es_un_registro(n) and not protegido(n)
    ]


def test_every_security_log_call_in_a_use_case_is_guarded():
    """
    Given: Los casos de uso de todos los módulos
    When: Se buscan sus llamadas al log de seguridad
    Then: Todas protegidas: un fallo del log nunca cambia la respuesta
    """
    sin_proteger = [s for f in CASOS_DE_USO for s in _sin_proteger(f)]

    assert sin_proteger == []


def test_the_guard_finds_the_use_cases():
    """El guardián mira de verdad: hay casos de uso y registros que revisar."""
    assert len(CASOS_DE_USO) > 50
    registros = [
        n for f in CASOS_DE_USO for n in ast.walk(ast.parse(f.read_text())) if _es_un_registro(n)
    ]
    assert len(registros) > 20


def _revisa(codigo: str, tmp_path) -> list[str]:
    fichero = tmp_path / "caso.py"
    fichero.write_text(codigo)
    return _sin_proteger(fichero)


def test_the_guard_sees_a_try_that_re_raises_as_unguarded(tmp_path):
    """Un try que vuelve a lanzar no protege nada (revisor de seguridad)."""
    codigo = (
        "def f(self):\n"
        "    try:\n"
        "        self._security_audit.log_x()\n"
        "    except Exception:\n"
        "        raise\n"
    )
    assert len(_revisa(codigo, tmp_path)) == 1


def test_the_guard_sees_any_receiver(tmp_path):
    """Con otro nombre para el log (un alias), también cuenta (revisor de seguridad)."""
    codigo = "def f(self):\n    audit = self._security_audit\n    audit.log_x()\n"
    assert len(_revisa(codigo, tmp_path)) == 1


def test_the_guard_accepts_a_try_that_swallows(tmp_path):
    codigo = (
        "def f(self):\n"
        "    try:\n"
        "        self._security_audit.log_x()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    assert _revisa(codigo, tmp_path) == []
