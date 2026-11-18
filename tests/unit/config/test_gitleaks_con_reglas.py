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


# --- B7, auditoría del 18 nov 2026 ----------------------------------------------------


def _paso(identificador: str) -> tuple[dict, dict]:
    """El paso con ese id y el job que lo contiene."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for paso in job.get("steps", []):
            if paso.get("id") == identificador:
                return job, paso
    raise AssertionError(f"No hay paso {identificador!r}")


def test_b7_1_the_ci_scans_the_whole_history_with_the_tested_binary():
    """
    Given: el paso «gitleaks» del CI
    When: se mira cómo escanea
    Then: `gitleaks git` sobre todo el historial (checkout con fetch-depth 0), con la config
          del repo y el mismo binario que la autoprueba; ya no la acción, que solo miraba los
          commits nuevos de la PR (INF-R3-02: el historial tenía una clave de Mailgun)
    """
    job, paso = _paso("gitleaks")
    _, autoprueba = _paso("gitleaks-self-test")

    assert "uses" not in paso, "La acción solo revisa el rango de la PR"
    assert re.search(r'gitleaks"? git \.', paso["run"])
    assert "--config .gitleaks.toml" in paso["run"]
    # Todo el historial y los merges, sin acotar a un rango (CodeRabbit: un secreto
    # metido al resolver un conflicto solo aparece en el parche del merge)
    opciones = re.search(r'--log-opts="([^"]*)"', paso["run"])
    assert opciones, "Sin --log-opts git log no saca el parche de los merges"
    assert {"--all", "--full-history", "--diff-merges=first-parent"} <= set(
        opciones.group(1).split()
    )
    assert ".." not in opciones.group(1), "Un rango revisaría solo parte del historial"
    assert "--redact" in paso["run"], "El valor del secreto no puede salir en el log del CI"
    assert "--verbose" in paso["run"], "Sin --verbose no se sabe dónde está el hallazgo"
    assert "$RUNNER_TEMP/gitleaks" in paso["run"], "Tiene que usar el binario comprobado"
    assert autoprueba["env"]["GITLEAKS_VERSION"] == "8.24.3"
    checkout = next(
        p for p in job["steps"] if str(p.get("uses", "")).startswith("actions/checkout")
    )
    assert checkout["with"]["fetch-depth"] == 0


def test_b7_3_the_self_test_requires_the_database_url_rule():
    """
    Given: la autoprueba del CI
    When: se mira qué reglas exige
    Then: también la de URLs de base de datos con contraseña
    """
    script = (RAIZ / ".github" / "scripts" / "gitleaks_self_test.sh").read_text(encoding="utf-8")

    assert "database-url-with-password" in script


def _regla_de_urls() -> dict:
    return next(r for r in _config()["rules"] if r["id"] == "database-url-with-password")


def _salta(regla: dict, texto: str, fichero: str = "src/config/settings.py") -> bool:
    """La regla vista en Python: casa, y ninguna de sus allowlists la excluye."""
    coincidencia = re.search(regla["regex"], texto)
    if not coincidencia:
        return False
    secreto = coincidencia.group(regla["secretGroup"])
    for lista in regla.get("allowlists", []):
        objetivo = coincidencia.group(0) if lista.get("regexTarget") == "match" else secreto
        por_texto = any(re.search(r, objetivo) for r in lista.get("regexes", []))
        rutas = lista.get("paths", [])
        por_ruta = any(re.search(r, fichero) for r in rutas)
        if lista.get("condition") == "AND" and rutas:
            if por_texto and por_ruta:
                return False
        elif por_texto or por_ruta:
            return False
    return True


def test_b7_3_the_rule_catches_a_real_database_url():
    """
    Given: URLs con la contraseña dentro hacia un host de verdad
    When: se pasan por la regla
    Then: salta en todas
    """
    regla = _regla_de_urls()
    for url in (
        "postgresql://rydercup_app:Zk81hQ2pLmW@dpg-abc-a.frankfurt-postgres.render.com/db",
        "postgres://dueno:s3cr3t-Larga@db.example.org:5432/rydercup",
        "postgresql+asyncpg://u:Abc123xyz!@10.0.0.5/base",
        "redis://:Zk81hQ2pLmW@cache.example.org:6379/0",  # Redis, sin usuario (revisión)
    ):
        assert _salta(regla, f'DATABASE_URL = "{url}"'), url


def test_b7_4_the_rule_skips_examples_and_local_databases():
    """
    Given: URLs de ejemplo con marcadores, y las de bases locales o de tests
    When: se pasan por la regla
    Then: no salta ninguna
    """
    regla = _regla_de_urls()
    for url in (
        "postgresql://USER:PASSWORD@host/db",
        "postgresql://user:${POSTGRES_PASSWORD}@host/db",
        "postgresql://user:$(POSTGRES_PASSWORD)@$(DATABASE_HOST):5432/db",
        "postgresql://user:<clave>@host/db",
        "postgresql://postgres:postgres@localhost:5432/rydercup",
        "postgresql://test:test_password@localhost/test",
    ):
        assert not _salta(regla, f'URL = "{url}"'), url


def test_b7_4_compose_and_ci_hosts_are_only_skipped_in_their_files():
    """
    Given: URLs hacia «db» (Compose) y «dummy» (CI)
    When: están en sus ficheros de ejemplo / en el código
    Then: en sus ficheros no saltan; en el código, sí (un host privado puede llamarse así)
    """
    regla = _regla_de_urls()
    compose = 'URL = "postgresql://postgres:otra-cosa@db:5432/rydercup"'
    ci = 'URL = "postgresql://dummy:dummy@dummy/dummy"'

    assert not _salta(regla, compose, "docker/docker-compose.yml")
    assert not _salta(regla, ci, ".github/workflows/ci_cd_pipeline.yml")
    assert _salta(regla, compose, "src/config/settings.py")
    assert _salta(regla, ci, "src/modules/x.py")


def test_b7_2_the_history_ignore_list_is_narrow():
    """
    Given: .gitleaksignore
    When: se lee cada línea que no es comentario
    Then: son huellas exactas (commit:fichero:regla:línea) de los ficheros ya revisados
          (el k8s/api-secret.yaml antiguo y los logs de pruebas), nunca rutas o comodines
    """
    lineas = [
        linea
        for linea in (RAIZ / ".gitleaksignore").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.startswith("#")
    ]

    assert lineas
    for linea in lineas:
        assert re.fullmatch(r"[0-9a-f]{40}:[^:*]+:[a-z0-9-]+:\d+", linea), linea
        fichero = linea.split(":")[1]
        assert fichero == "k8s/api-secret.yaml" or fichero.startswith("logs/security_audit.log."), (
            linea
        )
