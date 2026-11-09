"""
La imagen se instala desde `requirements.lock`, con un hash por paquete (OWASP A08,
F-18 de la auditoría del 9 nov 2026): si alguien sustituye un paquete en el índice,
pip se niega a instalarlo. El lock se genera desde `requirements.txt`, así que los
dos tienen que decir lo mismo; si no, la imagen instalaría otra versión de la que
se probó.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
PIN = re.compile(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([^\s;\\]+)", re.MULTILINE)


def _pines(fichero: str) -> dict[str, str]:
    """Paquete (normalizado) → versión, de cada línea `paquete==versión`."""
    texto = (RAIZ / fichero).read_text(encoding="utf-8")
    return {
        re.sub(r"[-_.]+", "-", nombre).lower(): version for nombre, version in PIN.findall(texto)
    }


def test_the_lock_pins_exactly_the_versions_of_requirements_txt():
    """
    Given: requirements.txt y requirements.lock
    When: se comparan sus versiones
    Then: cada paquete de requirements.txt está en el lock con la misma versión
    """
    directos = _pines("requirements.txt")
    bloqueados = _pines("requirements.lock")

    distintos = {
        nombre: (version, bloqueados.get(nombre))
        for nombre, version in directos.items()
        if bloqueados.get(nombre) != version
    }

    assert directos, "requirements.txt sin pines: la expresión no casa"
    assert distintos == {}, (
        "requirements.lock no coincide con requirements.txt; regenéralo con "
        f"scripts/freeze-requirements.sh: {distintos}"
    )


def test_every_locked_package_carries_a_hash():
    """
    Given: requirements.lock
    When: se mira cada paquete
    Then: todos llevan al menos un hash sha256 (con --require-hashes, pip se niega
          a instalar uno sin hash)
    """
    texto = (RAIZ / "requirements.lock").read_text(encoding="utf-8")
    bloques = re.split(r"\n(?=[A-Za-z0-9._-]+==)", texto)
    sin_hash = [
        b.split("\n", 1)[0]
        for b in bloques
        if "==" in b.split("\n", 1)[0] and "--hash=sha256:" not in b
    ]

    assert sin_hash == []


def test_the_image_installs_from_the_lock_with_hashes():
    """
    Given: el Dockerfile
    When: se mira cómo instala las dependencias
    Then: instala requirements.lock con --require-hashes, no requirements.txt
    """
    dockerfile = (RAIZ / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "--require-hashes" in dockerfile
    assert "-r requirements.lock" in dockerfile
    assert "-r requirements.txt" not in dockerfile


def test_the_image_runs_as_an_unprivileged_user():
    """
    Given: el Dockerfile
    When: se mira con qué usuario arranca
    Then: el último USER no es root (F-14: un fallo que ejecutara código lo haría
          sin privilegios dentro del contenedor)
    """
    lineas = (RAIZ / "docker" / "Dockerfile").read_text(encoding="utf-8").splitlines()
    usuarios = [linea.split()[1] for linea in lineas if linea.startswith("USER ")]

    assert usuarios, "el Dockerfile no declara USER: arranca como root"
    assert usuarios[-1] not in {"root", "0", "0:0"}
