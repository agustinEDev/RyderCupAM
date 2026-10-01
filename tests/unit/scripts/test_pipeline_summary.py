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
    L1   un check obligatorio fallado o cancelado sale con su estado en la tabla
         (salía «FAILED» sin decir cuál: CodeRabbit en la #446). Desde el 1 oct
         2026 el resumen es una tabla índice, una fila por check: ya no hay lista
    V1   el veredicto cuenta los checks que no pasaron
    V2   una ejecución en verde lo dice y tiene una fila por check
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


_FILAS = [
    ("unit_tests", "🧪 Unit tests"),
    ("integration_tests", "🗄️ Integration tests"),
    ("security_tests", "🔐 Security tests"),
    ("gpg_verification", "🔏 Signed commits"),
    ("architecture", "🏛️ Architecture"),
    ("api_contract", "📜 API contract"),
    ("owasp_semgrep", "🛡️ OWASP (Semgrep)"),
    ("linting", "📝 Lint & format"),
    ("type_checking", "🔬 Types (mypy)"),
    ("security_checks", "🔒 Security Checks"),
    ("dependency_review", "🔎 Dependency Review"),
    ("build", "🐳 Image"),
]
_NO_PASA = {"failure": "❌ failure", "cancelled": "⏹️ cancelled"}


def _fila(resumen, nombre):
    filas = [linea for linea in resumen.splitlines() if linea.startswith(f"| {nombre}")]
    assert len(filas) == 1, f"{nombre}: {filas}"
    return filas[0]


@pytest.mark.parametrize("resultado", list(_NO_PASA))
@pytest.mark.parametrize(("job", "nombre"), _FILAS, ids=[j for j, _ in _FILAS])
def test_l1_a_required_check_that_did_not_pass_is_named(tmp_path, job, nombre, resultado):
    """
    GIVEN: Un check obligatorio fallado o cancelado y lo demás en verde
    WHEN: Se ejecuta el resumen
    THEN: Sale con 1, el veredicto dice que falló y la fila de ese check lleva su estado
    """
    proceso, resumen = _ejecutar(tmp_path, {**_OK, job: resultado})

    assert proceso.returncode == 1
    assert resumen.startswith("## ❌ Pipeline failed — 1 check did not pass")
    assert _fila(resumen, nombre).endswith(f"| {_NO_PASA[resultado]} |")


def test_v1_the_verdict_counts_the_checks_that_did_not_pass(tmp_path):
    """
    GIVEN: Lint fallado, tipos cancelados y tests y build saltados por ello
    WHEN: Se ejecuta el resumen
    THEN: El veredicto dice 2 checks y avisa de que tests y build no corrieron
    """
    proceso, resumen = _ejecutar(
        tmp_path, {**_OK, **_SIN_COLUMNA_2, "linting": "failure", "type_checking": "cancelled"}
    )

    assert proceso.returncode == 1
    assert resumen.startswith("## ❌ Pipeline failed — 2 checks did not pass")
    assert "Tests and build are skipped" in resumen


def test_v2_a_green_run_says_so_and_lists_every_check(tmp_path):
    """
    GIVEN: Todos los jobs en verde
    WHEN: Se ejecuta el resumen
    THEN: Dice que pasó y cada check tiene su fila en verde
    """
    proceso, resumen = _ejecutar(tmp_path, _OK)

    assert proceso.returncode == 0
    assert resumen.startswith("## ✅ Pipeline passed")
    for _, nombre in [*_FILAS, ("sbom_generation", "📦 SBOM")]:
        assert _fila(resumen, nombre).endswith("| ✅ success |")
