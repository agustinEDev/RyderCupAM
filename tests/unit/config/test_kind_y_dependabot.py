"""
Endurecimiento del Kind local y de Dependabot (re-auditoría del 16 nov 2026).

- INF-09: el Kind publicaba la API, el front y su Postgres en todas las interfaces del
  Mac; en una wifi compartida cualquiera llegaba a ellos. Cada puerto, solo en localhost.
- INF-12: Dependabot proponía una versión el mismo día de publicarse, que es la ventana
  de los paquetes envenenados. Cada ecosistema espera unos días.
"""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[3]


def _puertos_del_kind() -> list[dict]:
    config = yaml.safe_load((RAIZ / "k8s" / "kind-config.yaml").read_text(encoding="utf-8"))
    return [m for nodo in config["nodes"] for m in nodo.get("extraPortMappings", [])]


def _actualizaciones() -> list[dict]:
    config = yaml.safe_load((RAIZ / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    return config["updates"]


def test_the_kind_publishes_ports():
    """
    Given: La configuración del clúster Kind
    When: Se leen sus puertos publicados
    Then: Hay alguno (si no, el test de abajo no comprobaría nada)
    """
    assert _puertos_del_kind()


@pytest.mark.parametrize("puerto", _puertos_del_kind(), ids=lambda m: str(m["hostPort"]))
def test_each_kind_port_listens_only_on_localhost(puerto):
    """
    Given: Un puerto que el Kind publica en el Mac
    When: Se mira en qué dirección escucha
    Then: Solo en 127.0.0.1, no en la red
    """
    assert puerto.get("listenAddress") == "127.0.0.1"


@pytest.mark.parametrize("actualizacion", _actualizaciones(), ids=lambda u: u["package-ecosystem"])
def test_each_dependabot_ecosystem_waits_before_proposing_a_new_release(actualizacion):
    """
    Given: Un ecosistema que vigila Dependabot
    When: Se mira su periodo de espera
    Then: Espera al menos 3 días antes de proponer una versión recién publicada
    """
    assert actualizacion.get("cooldown", {}).get("default-days", 0) >= 3
