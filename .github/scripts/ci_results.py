"""Números de verdad para las tarjetas de resumen del CI.

    ci_results.py pytest <junit.xml> [<coverage.xml>]
        «N passed, F failed[, E error(s)], S skipped in T s[ · coverage NN.N%]»
    ci_results.py trivy <trivy.sarif>
        «C CRITICAL, H HIGH» (hallazgos, de las etiquetas de la regla o del mensaje)

Imprime una línea. Si el informe no está o no se entiende lo dice y remite al
log: nunca inventa un número. Siempre sale con 0 (la tarjeta es informativa).
"""

import json
import re
import sys
import xml.etree.ElementTree as ET  # informes propios del job, no entrada externa
from pathlib import Path

_SIN_INFORME = "No test report (the tests did not run or crashed) — see the step log"
_SIN_SARIF = "No readable Trivy SARIF — see the step log"
_SEVERIDADES = ("CRITICAL", "HIGH")


def pytest_line(junit: Path, coverage: Path | None = None) -> str:
    try:
        raiz = ET.parse(junit).getroot()
        suites = [raiz] if raiz.tag == "testsuite" else list(raiz.iter("testsuite"))
        if not suites:
            return _SIN_INFORME

        def total(campo: str) -> int:
            return sum(int(suite.get(campo, 0)) for suite in suites)

        tests, fallos, errores, saltados = (
            total("tests"),
            total("failures"),
            total("errors"),
            total("skipped"),
        )
        segundos = sum(float(suite.get("time", 0)) for suite in suites)
    except (OSError, ET.ParseError, ValueError):
        return _SIN_INFORME

    pasados = tests - fallos - errores - saltados
    partes = [f"{pasados} passed", f"{fallos} failed"]
    if errores:
        partes.append(f"{errores} error{'s' if errores != 1 else ''}")
    partes.append(f"{saltados} skipped in {segundos:.0f} s")
    linea = ", ".join(partes)
    if coverage is not None:
        linea += " · " + _coverage(coverage)
    return linea


def _coverage(ruta: Path) -> str:
    try:
        tasa = float(ET.parse(ruta).getroot().get("line-rate"))
    except (OSError, ET.ParseError, TypeError, ValueError):
        return "coverage report not found"
    return f"coverage {tasa * 100:.1f}%"


def _severidad(resultado: dict, reglas: list, por_id: dict) -> str | None:
    regla = None
    indice = resultado.get("ruleIndex")
    if isinstance(indice, int) and 0 <= indice < len(reglas):
        regla = reglas[indice]
    regla = regla or por_id.get(resultado.get("ruleId"))
    etiquetas = ((regla or {}).get("properties") or {}).get("tags") or []
    for severidad in _SEVERIDADES:
        if severidad in etiquetas:
            return severidad
    texto = (resultado.get("message") or {}).get("text", "")
    encontrada = re.search(r"Severity:\s*([A-Z]+)", texto)
    return encontrada.group(1) if encontrada else None


def trivy_line(sarif: Path) -> str:
    try:
        datos = json.loads(Path(sarif).read_text(encoding="utf-8"))
        cuenta = dict.fromkeys(_SEVERIDADES, 0)
        for run in datos["runs"]:
            reglas = run.get("tool", {}).get("driver", {}).get("rules") or []
            por_id = {regla.get("id"): regla for regla in reglas}
            for resultado in run.get("results") or []:
                severidad = _severidad(resultado, reglas, por_id)
                if severidad in cuenta:
                    cuenta[severidad] += 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return _SIN_SARIF
    return ", ".join(f"{cuenta[s]} {s}" for s in _SEVERIDADES)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    orden, *rutas = argv or [""]
    try:
        if orden == "pytest" and rutas:
            print(pytest_line(Path(rutas[0]), Path(rutas[1]) if rutas[1:] else None))
        elif orden == "trivy" and rutas:
            print(trivy_line(Path(rutas[0])))
        else:
            print(f"::warning::ci_results.py: bad arguments {argv}")
            print("Could not read the results — see the step log")
    except Exception as error:  # la tarjeta nunca tumba el job
        print(f"Could not read the results ({error}) — see the step log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
