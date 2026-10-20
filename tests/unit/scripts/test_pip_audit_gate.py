"""
Tests de la puerta de pip-audit del CI (.github/scripts/pip_audit_gate.py).

Hasta el 30 sep 2026 solo bloqueaba si el identificador empezaba por «CVE»,
y pip-audit usa sobre todo PYSEC- y GHSA-: con jinja2==3.1.2, cinco
vulnerabilidades con arreglo, contaba cero. Y un informe ausente o roto
contaba como aprobado.

    #   informe                                  | sale
    ----|-----------------------------------------|------------------------------
    G1  una vulnerabilidad con arreglo (PYSEC)  | 1, y la nombra
    G2  con arreglo y id GHSA o CVE             | 1
    G3  solo sin arreglo                        | 0, avisando
    G4  sin vulnerabilidades                    | 0
    G5  el informe no está                      | 2
    G6  el informe no es JSON o no tiene forma  | 2
    G7  un paquete que pip-audit no pudo mirar  | no cuenta como vulnerable
    G8  en el CI, deja los números en la salida | total, con y sin arreglo
"""

import importlib.util
import json
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "pip_audit_gate.py"
_spec = importlib.util.spec_from_file_location("pip_audit_gate", _RUTA)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _informe(tmp_path, dependencias):
    ruta = tmp_path / "pip-audit-report.json"
    ruta.write_text(json.dumps({"dependencies": dependencias, "fixes": []}))
    return ruta


def _vuln(vid, fixes):
    return {"id": vid, "fix_versions": fixes, "aliases": [], "description": "x"}


def test_g1_a_fixable_pysec_vulnerability_blocks(tmp_path, capsys):
    """
    GIVEN: Un paquete con una vulnerabilidad PYSEC que tiene arreglo
    WHEN: Se pasa la puerta
    THEN: Sale con 1 y dice qué paquete y a qué versión subir
    """
    ruta = _informe(
        tmp_path,
        [{"name": "jinja2", "version": "3.1.2", "vulns": [_vuln("PYSEC-2024-1", ["3.1.3"])]}],
    )

    assert gate.main([str(ruta)]) == 1
    salida = capsys.readouterr().out
    assert "jinja2" in salida
    assert "3.1.3" in salida


@pytest.mark.parametrize("vid", ["GHSA-xxxx-yyyy-zzzz", "CVE-2026-1"])
def test_g2_any_identifier_with_a_fix_blocks(tmp_path, vid):
    """
    GIVEN: Una vulnerabilidad con arreglo, sea cual sea su identificador
    WHEN: Se pasa la puerta
    THEN: Sale con 1
    """
    ruta = _informe(tmp_path, [{"name": "a", "version": "1", "vulns": [_vuln(vid, ["2"])]}])

    assert gate.main([str(ruta)]) == 1


def test_g3_only_unfixable_vulnerabilities_pass_with_a_warning(tmp_path, capsys):
    """
    GIVEN: Solo vulnerabilidades sin versión que las arregle
    WHEN: Se pasa la puerta
    THEN: Sale con 0, pero las enseña
    """
    ruta = _informe(tmp_path, [{"name": "a", "version": "1", "vulns": [_vuln("PYSEC-1", [])]}])

    assert gate.main([str(ruta)]) == 0
    assert "PYSEC-1" in capsys.readouterr().out


def test_g4_no_vulnerabilities_passes(tmp_path):
    """
    GIVEN: Un informe sin vulnerabilidades
    WHEN: Se pasa la puerta
    THEN: Sale con 0
    """
    ruta = _informe(tmp_path, [{"name": "a", "version": "1", "vulns": []}])

    assert gate.main([str(ruta)]) == 0


def test_g5_a_missing_report_fails(tmp_path):
    """
    GIVEN: pip-audit no llegó a escribir el informe
    WHEN: Se pasa la puerta
    THEN: Sale con 2: no se ha comprobado nada, no es un aprobado
    """
    assert gate.main([str(tmp_path / "no-existe.json")]) == 2


@pytest.mark.parametrize("contenido", ["no es json", "{}", '{"dependencies": 3}', "[]"])
def test_g6_a_broken_report_fails(tmp_path, contenido):
    """
    GIVEN: Un informe que no es JSON o no tiene la forma de pip-audit
    WHEN: Se pasa la puerta
    THEN: Sale con 2
    """
    ruta = tmp_path / "pip-audit-report.json"
    ruta.write_text(contenido)

    assert gate.main([str(ruta)]) == 2


def test_g7_a_skipped_package_is_not_a_vulnerability(tmp_path):
    """
    GIVEN: Un paquete que pip-audit no pudo resolver (lleva skip_reason, sin vulns)
    WHEN: Se pasa la puerta
    THEN: Sale con 0
    """
    ruta = _informe(tmp_path, [{"name": "local-pkg", "skip_reason": "not on PyPI"}])

    assert gate.main([str(ruta)]) == 0


def test_g8_writes_the_counts_to_the_ci_output(tmp_path, monkeypatch):
    """
    GIVEN: El CI con su fichero de salidas
    WHEN: Se pasa la puerta con una vulnerabilidad con arreglo y otra sin él
    THEN: Deja total, con arreglo y sin arreglo
    """
    salidas = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salidas))
    ruta = _informe(
        tmp_path,
        [{"name": "a", "version": "1", "vulns": [_vuln("PYSEC-1", ["2"]), _vuln("PYSEC-2", [])]}],
    )

    gate.main([str(ruta)])

    lineas = salidas.read_text().splitlines()
    assert "total_vulnerabilities=2" in lineas
    assert "fixable_vulnerabilities=1" in lineas
    assert "unfixable_vulnerabilities=1" in lineas
