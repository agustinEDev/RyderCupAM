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
TRIVYIGNORE = RAIZ / ".trivyignore"


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


def test_the_ci_passes_the_current_day_to_the_image_build():
    """
    Given: el job de build del CI
    When: se mira el paso que construye la imagen
    Then: le pasa APT_REFRESH con el día, sacado de un paso anterior: la capa de paquetes
          se reconstruye una vez al día aunque el Dockerfile no cambie
    """
    pasos = _pasos_del_build()
    fecha = _paso(pasos, "apt_refresh")
    build = _paso(pasos, "image")

    assert "date -u +%F" in fecha["run"]
    assert pasos.index(fecha) < pasos.index(build)
    assert "APT_REFRESH=${{ steps.apt_refresh.outputs.day }}" in build["with"]["build-args"]


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


def test_every_accepted_vulnerability_has_a_reason_and_an_expiry():
    """
    Given: .trivyignore
    When: se mira cada vulnerabilidad aceptada
    Then: lleva fecha de caducidad (`exp:`) y un comentario con el motivo justo encima
    """
    lineas = TRIVYIGNORE.read_text(encoding="utf-8").splitlines()
    aceptadas = [(i, linea) for i, linea in enumerate(lineas) if linea.startswith("CVE-")]

    assert aceptadas
    for i, linea in aceptadas:
        assert re.fullmatch(r"CVE-\d{4}-\d+ exp:\d{4}-\d{2}-\d{2}", linea), linea
        assert i > 0 and lineas[i - 1].startswith("#"), f"Sin motivo encima: {linea}"
