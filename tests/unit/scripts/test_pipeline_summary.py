"""
Tests del paso «📊 Summary» del pipeline (.github/workflows/ci_cd_pipeline.yml).

Se extrae su script del YAML y se ejecuta con `bash -e`, como en GitHub, con
los resultados de los jobs sustituidos. Hasta el 30 sep 2026 salía en verde si
fallaban lint, tipos, Security Checks o Dependency Review: caía en «PARTIAL
SUCCESS» sin haber ejecutado un solo test.

    #    resultados                                         | sale
    -----|--------------------------------------------------|-----
    S1   todo bien                                         | 0
    S2   falla lint; tests y build saltados                | 1
    S3   Security Checks cancelado; lo demás saltado       | 1
    S4   solo falla el SBOM (informativo)                  | 0
    S5   fallan los unit                                   | 1
    S6   push a main: contrato y Dependency Review saltados | 0
    S7   falla Dependency Review; lo demás saltado         | 1
    Aislados, porque los dos mecanismos se tapan entre sí:
    S8   falla lint con el build en verde                  | 1
    S9   falla Dependency Review con el build en verde     | 1
    S10  Security Checks cancelado con el build en verde   | 1
    S11  build saltado con lo demás en verde               | 1
    J1   el script lee exactamente los jobs de sus `needs`, y son los de aquí
         (un job que no está en `needs` da "" en GitHub: dejaría de contar callado)
    L1   un check obligatorio cancelado sale en la lista de lo que no pasó
         (salía «FAILED» sin decir cuál: CodeRabbit en la #446)
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci_cd_pipeline.yml"

_JOBS = [
    "unit_tests",
    "integration_tests",
    "security_tests",
    "security_checks",
    "dependency_review",
    "sbom_generation",
    "gpg_verification",
    "linting",
    "type_checking",
    "build",
    "architecture",
    "api_contract",
    "owasp_semgrep",
]
_OK = dict.fromkeys(_JOBS, "success")
_SIN_COLUMNA_2 = {
    "unit_tests": "skipped",
    "integration_tests": "skipped",
    "security_tests": "skipped",
    "build": "skipped",
}

ESCENARIOS = [
    ("S1", {}, 0),
    ("S2", {"linting": "failure", **_SIN_COLUMNA_2}, 1),
    ("S3", {"security_checks": "cancelled", **_SIN_COLUMNA_2}, 1),
    ("S4", {"sbom_generation": "failure"}, 0),
    ("S5", {"unit_tests": "failure"}, 1),
    ("S6", {"api_contract": "skipped", "dependency_review": "skipped"}, 0),
    ("S7", {"dependency_review": "failure", **_SIN_COLUMNA_2}, 1),
    ("S8", {"linting": "failure"}, 1),
    ("S9", {"dependency_review": "failure"}, 1),
    ("S10", {"security_checks": "cancelled"}, 1),
    ("S11", {"build": "skipped"}, 1),
]


def _ejecutar(tmp_path, resultados):
    script = re.sub(
        r"\$\{\{\s*needs\.(\w+)\.result\s*\}\}",
        lambda m: resultados.get(m.group(1), ""),
        _script_del_resumen(),
    )
    script = re.sub(r"\$\{\{[^}]*\}\}", "x", script)
    fichero = tmp_path / "resumen.sh"
    fichero.write_text(script)
    salida = tmp_path / "summary.md"
    salida.write_text("")
    proceso = subprocess.run(
        ["bash", "-e", str(fichero)],
        env={
            "GITHUB_STEP_SUMMARY": str(salida),
            "GITHUB_OUTPUT": str(tmp_path / "output"),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return proceso, salida.read_text()


def _script_del_resumen() -> str:
    flujo = yaml.safe_load(_WORKFLOW.read_text())
    pasos = flujo["jobs"]["pipeline_summary"]["steps"]
    return "\n".join(paso["run"] for paso in pasos if "run" in paso)


@pytest.mark.parametrize(
    ("caso", "cambios", "esperado"), ESCENARIOS, ids=[e[0] for e in ESCENARIOS]
)
def test_the_summary_fails_whenever_a_required_check_did_not_pass(
    tmp_path, caso, cambios, esperado
):
    """
    GIVEN: Los resultados de los jobs de un escenario
    WHEN: Se ejecuta el script del resumen con bash -e
    THEN: Sale con 1 si algo obligatorio no pasó, y con 0 si no
    """
    resultados = {**_OK, **cambios}
    script = re.sub(
        r"\$\{\{\s*needs\.(\w+)\.result\s*\}\}",
        # Como en GitHub: un job fuera de `needs` no tiene resultado
        lambda m: resultados.get(m.group(1), ""),
        _script_del_resumen(),
    )
    script = re.sub(r"\$\{\{[^}]*\}\}", "x", script)
    fichero = tmp_path / "resumen.sh"
    fichero.write_text(script)
    salida = tmp_path / "summary.md"

    proceso = subprocess.run(
        ["bash", "-e", str(fichero)],
        env={
            "GITHUB_STEP_SUMMARY": str(salida),
            "GITHUB_OUTPUT": str(salida),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert proceso.returncode == esperado, f"{caso}: {proceso.stderr[-500:]}"


def test_j1_the_summary_reads_exactly_the_jobs_it_needs():
    """
    GIVEN: El paso de resumen y la lista `needs` de su job
    WHEN: Se comparan los jobs que lee con los que espera y con los de este test
    THEN: Son los mismos: renombrar o quitar uno no lo deja fuera sin avisar
    """
    flujo = yaml.safe_load(_WORKFLOW.read_text())
    necesita = set(flujo["jobs"]["pipeline_summary"]["needs"])
    leidos = set(re.findall(r"needs\.(\w+)\.result", _script_del_resumen()))

    assert leidos == necesita
    assert necesita == set(_JOBS)
    assert necesita <= set(flujo["jobs"])


_EN_LA_LISTA = [
    ("unit_tests", "**Unit Tests**"),
    ("integration_tests", "**Integration Tests**"),
    ("security_tests", "**Security Tests**"),
    ("gpg_verification", "**GPG Verification**"),
    ("architecture", "**Architecture Contracts**"),
    ("api_contract", "**API Contract**"),
    ("owasp_semgrep", "**OWASP Top 10 (Semgrep)**"),
    ("linting", "**Lint & format**"),
    ("type_checking", "**Types**"),
    ("security_checks", "**Security Checks**"),
    ("dependency_review", "**Dependency Review**"),
]


@pytest.mark.parametrize(("job", "texto"), _EN_LA_LISTA, ids=[j for j, _ in _EN_LA_LISTA])
def test_l1_a_cancelled_required_check_is_listed(tmp_path, job, texto):
    """
    GIVEN: Un check obligatorio cancelado y lo demás en verde
    WHEN: Se ejecuta el resumen
    THEN: Sale con 1 y ese check aparece en la lista de lo que no pasó
    """
    proceso, resumen = _ejecutar(tmp_path, {**_OK, job: "cancelled"})

    assert proceso.returncode == 1
    assert f"❌ {texto}" in resumen
