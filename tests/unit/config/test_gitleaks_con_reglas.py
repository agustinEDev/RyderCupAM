"""
Gitleaks tiene que detectar secretos (INF-01, auditoría del 16 nov 2026).

El `.gitleaks.toml` solo traía `[allowlist]`, sin `[[rules]]` ni `[extend]`: gitleaks
cargaba CERO reglas y el check «Security Checks» pasaba con cualquier secreto. Además la
allowlist saltaba cualquier fichero con «test» en la ruta (`latest_*.py`, `contest.py`) y
cualquier secreto con «test» o «example» dentro.

Estos tests fijan la forma de la config; la prueba de verdad (que gitleaks encuentra un
secreto sintético con esta config) la hace el paso «Gitleaks self-test» del CI.
"""

import re
import tomllib
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[3]
CONFIG = RAIZ / ".gitleaks.toml"
WORKFLOW = RAIZ / ".github" / "workflows" / "ci_cd_pipeline.yml"


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def _allowlists(config: dict) -> list[dict]:
    """La allowlist global, en su forma vieja (`[allowlist]`) o nueva (`[[allowlists]]`)."""
    listas = list(config.get("allowlists", []))
    if "allowlist" in config:
        listas.append(config["allowlist"])
    return listas


def test_the_config_loads_the_default_gitleaks_rules():
    """
    Given: .gitleaks.toml
    When: se lee la sección [extend]
    Then: usa las reglas por defecto de gitleaks (sin ellas no hay ni una regla)
    """
    config = _config()

    assert config.get("extend", {}).get("useDefault") is True, (
        "Sin `[extend] useDefault = true` gitleaks no carga ninguna regla"
    )


def test_the_path_allowlist_only_skips_the_tests_folder():
    """
    Given: la allowlist de rutas
    When: se mira cada expresión
    Then: todas están ancladas al principio de la ruta, y la de tests es `^tests/`
          (antes `.*test.*\\.py` saltaba `latest_x.py` o `src/contest.py`)
    """
    rutas = [r for lista in _allowlists(_config()) for r in lista.get("paths", [])]

    assert rutas, "Sin allowlist de rutas los tests con tokens de ejemplo saltarían"
    for ruta in rutas:
        assert ruta.startswith("^"), f"Ruta sin anclar en la allowlist: {ruta!r}"
    assert "^tests/" in rutas
    assert not any(re.search(ruta, "src/modules/competition/contest.py") for ruta in rutas)
    assert not any(re.search(ruta, "src/config/latest_settings.py") for ruta in rutas)


def test_no_generic_stopword_hides_a_real_secret():
    """
    Given: las stopwords de la allowlist
    When: se comparan con palabras que aparecen en secretos reales
    Then: no hay stopwords genéricas («test», «example», «mock»…), que tapaban un secreto
          real con solo contener esa palabra
    """
    genericas = {"test", "example", "mock", "fake", "placeholder"}
    stopwords = {s.lower() for lista in _allowlists(_config()) for s in lista.get("stopwords", [])}

    assert stopwords & genericas == set()


def test_the_ci_runs_a_self_test_that_requires_gitleaks_to_find_a_secret():
    """
    Given: el job de Security Checks del CI
    When: se buscan sus pasos
    Then: hay un paso de autoprueba que pasa la config del repo a gitleaks sobre un
          secreto sintético y falla si no lo encuentra, antes del escaneo de verdad
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    pasos = [
        paso
        for job in workflow["jobs"].values()
        for paso in job.get("steps", [])
        if paso.get("id") in {"gitleaks-self-test", "gitleaks"}
    ]
    ids = [paso["id"] for paso in pasos]

    assert ids == ["gitleaks-self-test", "gitleaks"], (
        f"La autoprueba tiene que ir justo antes del escaneo: {ids}"
    )
    assert ".github/scripts/gitleaks_self_test.sh" in pasos[0]["run"]
    script = (RAIZ / ".github" / "scripts" / "gitleaks_self_test.sh").read_text(encoding="utf-8")
    assert "--config .gitleaks.toml" in script
    assert "--exit-code" in script
