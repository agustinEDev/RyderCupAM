"""
Tests de los números que leen las tarjetas del CI (.github/scripts/ci_results.py).

Cada tarjeta de resumen cuenta lo que ha salido de verdad: tests pasados y
fallados con su duración y cobertura (del JUnit XML de pytest y de coverage.xml)
y hallazgos de Trivy por severidad (de su SARIF). Si un informe no está o no se
entiende, se dice así: nunca se inventa un número.

    #   entrada                                        | línea que sale
    ----|----------------------------------------------|----------------------------------
    R1  JUnit todo en verde                          | «N passed, 0 failed, S skipped in T s»
    R2  JUnit con fallos y errores                   | cuenta los dos, y no los da por pasados
    R3  JUnit con varias testsuite (raíz testsuites) | suma todas
    R4  con coverage.xml                             | añade «coverage NN.N%»
    R5  coverage.xml pedido pero ausente             | lo dice, sin inventar
    R6  JUnit ausente o roto                         | «No test report» y «see the step log»
    R7  SARIF de Trivy, severidad en las etiquetas   | cuenta por CRITICAL y HIGH
    R8  SARIF sin etiquetas: «Severity: X» en el texto | cuenta igual
    R9  SARIF sin hallazgos                          | «0 CRITICAL, 0 HIGH»
    R10 SARIF ausente o roto                         | lo dice y remite al log
    R11 argumentos rotos                             | sale con 0, avisando
"""

import importlib.util
import json
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "ci_results.py"
_spec = importlib.util.spec_from_file_location("ci_results", _RUTA)
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)


def _junit(tmp_path, *suites, raiz="testsuites"):
    cuerpo = "".join(
        f'<testsuite name="pytest" tests="{t}" failures="{f}" errors="{e}" '
        f'skipped="{s}" time="{tiempo}"></testsuite>'
        for t, f, e, s, tiempo in suites
    )
    if raiz == "testsuite":
        t, f, e, s, tiempo = suites[0]
        cuerpo = (
            f'<testsuite name="pytest" tests="{t}" failures="{f}" errors="{e}" '
            f'skipped="{s}" time="{tiempo}"></testsuite>'
        )
    else:
        cuerpo = f"<testsuites>{cuerpo}</testsuites>"
    ruta = tmp_path / "junit.xml"
    ruta.write_text(f'<?xml version="1.0" encoding="utf-8"?>{cuerpo}')
    return ruta


def test_r1_all_green(tmp_path):
    """
    GIVEN: Un JUnit de pytest con 100 tests, 3 saltados y ninguno fallado
    WHEN: Se resume
    THEN: Dice 97 pasados, 0 fallados, 3 saltados y los segundos
    """
    ruta = _junit(tmp_path, (100, 0, 0, 3, 45.6), raiz="testsuite")

    assert ci.pytest_line(ruta) == "97 passed, 0 failed, 3 skipped in 46 s"


def test_r2_failures_and_errors_are_not_passed(tmp_path):
    """
    GIVEN: Un JUnit con 2 fallos y 1 error
    WHEN: Se resume
    THEN: Cuenta los dos y no los suma a los pasados
    """
    ruta = _junit(tmp_path, (10, 2, 1, 0, 3.2))

    assert ci.pytest_line(ruta) == "7 passed, 2 failed, 1 error, 0 skipped in 3 s"


def test_r3_several_suites_are_added(tmp_path):
    """
    GIVEN: Un JUnit con dos testsuite
    WHEN: Se resume
    THEN: Suma las dos
    """
    ruta = _junit(tmp_path, (5, 1, 0, 1, 1.0), (5, 0, 0, 0, 2.0))

    assert ci.pytest_line(ruta) == "8 passed, 1 failed, 1 skipped in 3 s"


def test_r4_coverage_is_added(tmp_path):
    """
    GIVEN: Un JUnit y un coverage.xml con line-rate 0.9137
    WHEN: Se resume con la cobertura
    THEN: Añade «coverage 91.4%»
    """
    ruta = _junit(tmp_path, (1, 0, 0, 0, 0.4))
    cobertura = tmp_path / "coverage.xml"
    cobertura.write_text('<?xml version="1.0" ?><coverage line-rate="0.9137"></coverage>')

    assert (
        ci.pytest_line(ruta, cobertura) == "1 passed, 0 failed, 0 skipped in 0 s · coverage 91.4%"
    )


def test_r5_missing_coverage_is_said(tmp_path):
    """
    GIVEN: Un JUnit válido y un coverage.xml que no está
    WHEN: Se resume con la cobertura
    THEN: Dice que no hay informe de cobertura, sin inventar un porcentaje
    """
    ruta = _junit(tmp_path, (1, 0, 0, 0, 0.4))

    linea = ci.pytest_line(ruta, tmp_path / "coverage.xml")

    assert linea.startswith("1 passed")
    assert "coverage report not found" in linea
    assert "%" not in linea


@pytest.mark.parametrize("contenido", [None, "esto no es xml", "<otra/>"])
def test_r6_missing_or_broken_junit(tmp_path, contenido):
    """
    GIVEN: Un JUnit que no está, no es XML o no tiene testsuite
    WHEN: Se resume
    THEN: Lo dice y remite al log, sin números
    """
    ruta = tmp_path / "junit.xml"
    if contenido is not None:
        ruta.write_text(contenido)

    linea = ci.pytest_line(ruta)

    assert "No test report" in linea
    assert "see the step log" in linea


def _sarif(tmp_path, reglas, resultados):
    ruta = tmp_path / "trivy.sarif"
    ruta.write_text(
        json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {"tool": {"driver": {"name": "Trivy", "rules": reglas}}, "results": resultados}
                ],
            }
        )
    )
    return ruta


def _regla(rid, severidad):
    return {
        "id": rid,
        "properties": {"tags": ["vulnerability", "security", severidad]},
    }


def test_r7_trivy_counts_by_rule_tags(tmp_path):
    """
    GIVEN: Un SARIF con 1 CRITICAL y 2 HIGH (uno de ellos dos veces)
    WHEN: Se cuentan
    THEN: Cuenta hallazgos: 1 CRITICAL, 3 HIGH
    """
    reglas = [_regla("CVE-1", "CRITICAL"), _regla("CVE-2", "HIGH"), _regla("CVE-3", "HIGH")]
    resultados = [
        {"ruleId": "CVE-1", "ruleIndex": 0, "message": {"text": "x"}},
        {"ruleId": "CVE-2", "ruleIndex": 1, "message": {"text": "x"}},
        {"ruleId": "CVE-2", "ruleIndex": 1, "message": {"text": "x"}},
        {"ruleId": "CVE-3", "message": {"text": "x"}},
    ]

    assert ci.trivy_line(_sarif(tmp_path, reglas, resultados)) == "1 CRITICAL, 3 HIGH"


def test_r8_trivy_reads_the_message_when_rules_have_no_tags(tmp_path):
    """
    GIVEN: Un SARIF cuyas reglas no llevan la severidad en las etiquetas
    WHEN: Se cuentan
    THEN: La saca de «Severity: X» del mensaje
    """
    resultados = [
        {"ruleId": "CVE-9", "message": {"text": "Package: x\nSeverity: CRITICAL\nFixed: 2"}},
    ]

    assert ci.trivy_line(_sarif(tmp_path, [{"id": "CVE-9"}], resultados)) == "1 CRITICAL, 0 HIGH"


def test_r9_trivy_without_findings(tmp_path):
    """
    GIVEN: Un SARIF sin resultados
    WHEN: Se cuentan
    THEN: 0 CRITICAL, 0 HIGH
    """
    assert ci.trivy_line(_sarif(tmp_path, [], [])) == "0 CRITICAL, 0 HIGH"


@pytest.mark.parametrize("contenido", [None, "{roto", '{"runs": 3}'])
def test_r10_missing_or_broken_sarif(tmp_path, contenido):
    """
    GIVEN: Un SARIF que no está, no es JSON o no tiene la forma
    WHEN: Se cuentan
    THEN: Lo dice y remite al log
    """
    ruta = tmp_path / "trivy.sarif"
    if contenido is not None:
        ruta.write_text(contenido)

    linea = ci.trivy_line(ruta)

    assert "SARIF" in linea
    assert "see the step log" in linea


@pytest.mark.parametrize("argv", [[], ["nope"], ["pytest"], ["trivy"]])
def test_r11_bad_arguments_never_fail(argv, capsys):
    """
    GIVEN: Una llamada con argumentos rotos
    WHEN: Se ejecuta
    THEN: Sale con 0 y escribe algo honesto, sin lanzar
    """
    assert ci.main(argv) == 0
    assert "see the step log" in capsys.readouterr().out
