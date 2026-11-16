"""
El CI prueba y audita lo mismo que se despliega (re-auditoría del 16 nov 2026).

- INF-05: los tests, mypy, bandit y pip-audit corrían sobre una resolución nueva y sin
  hashes de requirements-dev.txt, mientras la imagen instala requirements.lock. Ahora
  cada job instala antes el lock exacto con --require-hashes (y pip desde su lock de
  arranque), después las herramientas de desarrollo, y comprueba que ninguna versión del
  lock se ha movido.
- INF-04: el generador del SBOM se instala desde su propio lock con hashes, y el paso que
  tiene el token no ejecuta ninguna herramienta instalada.
- INF-03: el SBOM se genera desde requirements.lock (los 55 paquetes que se instalan), no
  desde requirements.txt (31).
"""

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[3]
FLUJOS = RAIZ / ".github" / "workflows"


def _pasos(fichero: str) -> list[tuple[str, dict]]:
    """(job, paso) de cada paso con `run` del workflow."""
    flujo = yaml.safe_load((FLUJOS / fichero).read_text(encoding="utf-8"))
    return [
        (nombre, paso)
        for nombre, job in flujo["jobs"].items()
        for paso in job.get("steps", [])
        if "run" in paso
    ]


def _ordenes(run: str) -> list[str]:
    """Las órdenes de un `run`, sin comentarios y con las continuaciones unidas."""
    lineas = [x for x in run.replace("\\\n", " ").splitlines() if not x.strip().startswith("#")]
    return [x.strip() for x in lineas if x.strip()]


def _instalaciones(fichero: str) -> list[tuple[str, str, list[str]]]:
    return [
        (job, paso.get("name", ""), _ordenes(paso["run"]))
        for job, paso in _pasos(fichero)
        if "pip install" in paso["run"]
    ]


def test_every_ci_job_installs_the_shipped_lock_before_the_dev_tools():
    """
    Given: los pasos del CI y de Snyk que instalan dependencias de Python
    When: instalan requirements-dev.txt o requirements.txt
    Then: antes instalan pip desde requirements-bootstrap.lock y requirements.lock, los
          dos con --require-hashes, y después comprueban que el lock sigue intacto
    """
    revisados = 0
    for fichero in ("ci_cd_pipeline.yml", "snyk_review.yml"):
        for job, nombre, ordenes in _instalaciones(fichero):
            texto = "\n".join(ordenes)
            # Las que instalan el proyecto (no una herramienta suelta sacada de un fichero)
            if not re.search(r"-r requirements(-dev)?\.(txt|lock)\b", texto):
                continue
            revisados += 1
            donde = f"{fichero} · {job} · {nombre}"
            arranque = next(
                (i for i, o in enumerate(ordenes) if "-r requirements-bootstrap.lock" in o), None
            )
            lock = next((i for i, o in enumerate(ordenes) if "-r requirements.lock" in o), None)
            resto = next(
                (
                    i
                    for i, o in enumerate(ordenes)
                    if "-r requirements-dev.txt" in o or "-r requirements.txt" in o
                ),
                None,
            )
            assert arranque is not None and "--require-hashes" in ordenes[arranque], donde
            assert lock is not None and "--require-hashes" in ordenes[lock], donde
            assert resto is None or arranque < lock < resto, donde
            despues = ordenes[(resto if resto is not None else lock) + 1 :]
            assert any("comprobar_lock_instalado.py" in o for o in despues), donde

    assert revisados >= 7, revisados


def test_no_ci_step_upgrades_pip_without_a_version_and_a_hash():
    """
    Given: los workflows de Python
    When: se buscan instalaciones de pip
    Then: ninguna es `pip install --upgrade pip` (sin versión ni hash)
    """
    for fichero in ("ci_cd_pipeline.yml", "snyk_review.yml"):
        for job, nombre, ordenes in _instalaciones(fichero):
            for orden in ordenes:
                assert "--upgrade pip" not in orden, f"{fichero} · {job} · {nombre}"


def test_the_sbom_comes_from_the_lock_and_its_tool_from_a_hashed_lock():
    """
    Given: el job del SBOM
    When: se miran sus pasos
    Then: instala el generador con --require-hashes desde su lock, genera el SBOM desde
          requirements.lock y el paso que tiene el token no ejecuta cyclonedx-py
    """
    pasos = [p for job, p in _pasos("ci_cd_pipeline.yml") if job == "sbom_generation"]
    texto = {p.get("name", ""): p["run"] for p in pasos}

    instalar = next(r for r in texto.values() if "cyclonedx-bom" in r or "sbom-tools" in r)
    assert "--require-hashes" in instalar
    assert "-r .github/sbom-tools.lock" in instalar

    generar = next(r for r in texto.values() if "cyclonedx-py requirements" in r)
    assert re.search(r"cyclonedx-py requirements requirements\.lock\b", generar)

    con_token = [p for p in pasos if "GITHUB_TOKEN" in (p.get("env") or {})]
    assert con_token
    for paso in con_token:
        assert "cyclonedx-py" not in paso["run"]
        assert "pip install" not in paso["run"]

    guion = (RAIZ / "scripts" / "submit-sbom-to-github.sh").read_text(encoding="utf-8")
    assert "cyclonedx-py --version" not in guion
    assert '"requirements.lock"' in guion


def test_the_sbom_tool_lock_pins_its_source_with_hashes():
    """
    Given: .github/sbom-tools.txt y su lock
    When: se comparan
    Then: el lock fija cyclonedx-bom a la versión de la fuente y todo lleva hash
    """
    fuente = (RAIZ / ".github" / "sbom-tools.txt").read_text(encoding="utf-8")
    lock = (RAIZ / ".github" / "sbom-tools.lock").read_text(encoding="utf-8")

    version = re.search(r"^cyclonedx-bom==(\S+)", fuente, re.M)
    assert version
    assert f"cyclonedx-bom=={version.group(1)}" in lock
    bloques = [b for b in re.split(r"\n(?=[A-Za-z0-9._-]+==)", lock) if "==" in b.split("\n")[0]]
    assert bloques
    assert all("--hash=sha256:" in b for b in bloques)


def test_the_installed_lock_check_finds_a_moved_version(tmp_path, monkeypatch):
    """
    Given: un lock con un paquete en una versión que no es la instalada
    When: se ejecuta la comprobación del CI
    Then: termina con error y nombra el paquete
    """
    import importlib.util

    ruta = RAIZ / ".github" / "scripts" / "comprobar_lock_instalado.py"
    spec = importlib.util.spec_from_file_location("comprobar_lock_instalado", ruta)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    lock = tmp_path / "requirements.lock"
    lock.write_text("pyyaml==0.0.1 \\\n    --hash=sha256:abc\n", encoding="utf-8")

    distintos = modulo.distintos(lock)

    assert "pyyaml" in distintos
    assert distintos["pyyaml"][0] == "0.0.1"
