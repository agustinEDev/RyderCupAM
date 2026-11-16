"""
La imagen tiene que llevar los parches de Debian del día (INF-02, auditoría del 16 nov 2026).

El `apt-get upgrade` del Dockerfile solo corre cuando se reconstruye su capa, y con la
caché de capas del CI (gha) se reutilizaba la de la primera vez: Trivy escaneaba zlib1g y
apt de finales de septiembre, con CVE HIGH ya arreglados, y su puerta solo paraba las
CRITICAL. Estos tests fijan las tres piezas: la capa de paquetes depende de un ARG, el CI
le pasa el día, y la puerta de Trivy para las HIGH y CRITICAL que tienen arreglo.
"""

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[3]
DOCKERFILE = RAIZ / "docker" / "Dockerfile"
WORKFLOW = RAIZ / ".github" / "workflows" / "ci_cd_pipeline.yml"
TRIVYIGNORE = RAIZ / ".trivyignore.yaml"


def _pasos_del_build() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["build"]["steps"]


def _paso(pasos: list[dict], id_: str) -> dict:
    return next(paso for paso in pasos if paso.get("id") == id_)


def test_the_base_image_is_pinned_by_digest():
    """
    Given: el Dockerfile
    When: se lee el FROM
    Then: la imagen base va fijada por digest (lo renueva Dependabot)
    """
    texto = DOCKERFILE.read_text(encoding="utf-8")

    assert re.search(r"^FROM python:[\d.]+-slim@sha256:[0-9a-f]{64}$", texto, re.MULTILINE)


def test_the_os_packages_layer_depends_on_a_refresh_argument():
    """
    Given: el Dockerfile
    When: se busca la capa del apt-get upgrade
    Then: va después de `ARG APT_REFRESH` y lo usa, así que un valor nuevo la reconstruye
          aunque haya caché
    """
    texto = DOCKERFILE.read_text(encoding="utf-8")
    arg = texto.find("ARG APT_REFRESH")
    upgrade = texto.find("apt-get upgrade")
    run = texto.rfind("RUN", 0, upgrade)

    assert arg != -1, "Falta `ARG APT_REFRESH` en el Dockerfile"
    assert arg < run, "El ARG tiene que ir antes de la capa del apt-get upgrade"
    assert "${APT_REFRESH}" in texto[run:upgrade]


def test_refreshing_the_os_packages_does_not_reinstall_python_packages():
    """
    Given: el Dockerfile
    When: se ordenan el ARG, el pip install, el apt-get upgrade y el cambio de usuario
    Then: el ARG y el upgrade van DESPUÉS del pip install (un APT_REFRESH nuevo no tira
          su caché) y antes de `USER app` (el upgrade necesita root); en la imagen final
          los paquetes del SO quedan al día
    """
    texto = DOCKERFILE.read_text(encoding="utf-8")
    pip = texto.find("--require-hashes -r requirements.lock")
    arg = texto.find("ARG APT_REFRESH")
    upgrade = texto.find("apt-get upgrade")
    usuario = texto.find("\nUSER app")

    assert -1 not in (pip, arg, upgrade, usuario)
    assert pip < arg < upgrade < usuario
    assert texto.count("apt-get upgrade") == 1


def test_the_ci_computes_the_day_once_for_the_three_image_builds():
    """
    Given: el job de build del CI, una matriz de tres entradas (build, render, trivy) que
           construyen cada una su imagen
    When: se mira de dónde sale APT_REFRESH
    Then: de un job previo que calcula el día UNA vez y del que depende build: las tres
          construyen la misma imagen aunque una arranque tras la medianoche UTC, y Trivy
          escanea la misma que guarda el build
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    dia = workflow["jobs"]["apt_refresh"]
    build = workflow["jobs"]["build"]
    imagen = _paso(build["steps"], "image")

    assert "date -u +%F" in "".join(paso.get("run", "") for paso in dia["steps"])
    assert dia["outputs"]["day"]
    assert "apt_refresh" in build["needs"]
    assert "APT_REFRESH=${{ needs.apt_refresh.outputs.day }}" in imagen["with"]["build-args"]
    assert not any("date -u" in paso.get("run", "") for paso in build["steps"])


def test_the_trivy_gate_blocks_fixable_high_and_critical():
    """
    Given: la puerta de Trivy
    When: se leen sus opciones
    Then: falla con cualquier HIGH o CRITICAL que tenga arreglo
    """
    puerta = _paso(_pasos_del_build(), "trivy_gate")["with"]

    assert set(puerta["severity"].split(",")) == {"HIGH", "CRITICAL"}
    assert puerta["ignore-unfixed"] is True
    assert str(puerta["exit-code"]) == "1"


def test_every_accepted_vulnerability_is_scoped_explained_and_expiring():
    """
    Given: .trivyignore.yaml
    When: se mira cada vulnerabilidad aceptada
    Then: va acotada a un paquete y versión concretos (purl), con su motivo (statement)
          y fecha de caducidad; y no queda un .trivyignore de texto, que la aceptaría en
          cualquier paquete de la imagen
    """
    aceptadas = yaml.safe_load(TRIVYIGNORE.read_text(encoding="utf-8"))["vulnerabilities"]

    assert aceptadas
    assert not (RAIZ / ".trivyignore").exists()
    for vulnerabilidad in aceptadas:
        assert re.fullmatch(r"CVE-\d{4}-\d+", vulnerabilidad["id"])
        assert vulnerabilidad["purls"]
        for purl in vulnerabilidad["purls"]:
            assert re.fullmatch(r"pkg:[a-z]+/[\w.-]+@[\w.+-]+", purl), purl
        assert len(vulnerabilidad["statement"]) > 40
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(vulnerabilidad["expired_at"]))


def test_both_trivy_steps_use_the_scoped_ignore_file():
    """
    Given: el escaneo de Trivy (SARIF) y su puerta
    When: se leen sus opciones
    Then: los dos usan .trivyignore.yaml
    """
    pasos = _pasos_del_build()

    for id_ in ("trivy_scan", "trivy_gate"):
        assert _paso(pasos, id_)["with"]["trivyignores"] == ".trivyignore.yaml"
