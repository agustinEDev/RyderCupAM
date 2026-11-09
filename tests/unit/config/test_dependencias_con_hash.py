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


def test_pip_itself_is_installed_pinned_and_with_hashes():
    """
    Given: el Dockerfile y requirements-bootstrap.lock
    When: se mira cómo se pone pip al día
    Then: desde el lock de arranque, con --require-hashes, y no con un
          `pip install --upgrade pip` sin versión ni hash (revisión de la fase 2):
          el pip que instala todo lo demás también se verifica
    """
    dockerfile = (RAIZ / "docker" / "Dockerfile").read_text(encoding="utf-8")
    instalaciones = [
        linea for linea in dockerfile.replace("\\\n", " ").splitlines() if "pip install" in linea
    ]

    assert "--require-hashes -r requirements-bootstrap.lock" in dockerfile
    assert "--upgrade pip" not in dockerfile
    for linea in instalaciones:
        for orden in linea.split("&&"):
            if "pip install" in orden:
                assert "--require-hashes" in orden, orden


def test_the_bootstrap_lock_pins_pip_like_its_source_and_with_hashes():
    """
    Given: requirements-bootstrap.txt y su lock
    When: se comparan
    Then: el lock fija pip a la versión de la fuente, con su hash
    """
    fuente = _pines("requirements-bootstrap.txt")
    lock = _pines("requirements-bootstrap.lock")
    texto = (RAIZ / "requirements-bootstrap.lock").read_text(encoding="utf-8")

    assert set(fuente) == {"pip"}
    assert lock == fuente
    assert "--hash=sha256:" in texto


def test_the_locks_are_resolved_for_the_platform_of_render():
    """
    Given: scripts/freeze-requirements.sh
    When: se mira cómo arranca la imagen que resuelve los locks
    Then: con --platform linux/amd64 (Render): en un Mac ARM saldrían otras ruedas; y
          compila los dos locks
    """
    guion = (RAIZ / "scripts" / "freeze-requirements.sh").read_text(encoding="utf-8")

    assert "docker run --rm --platform linux/amd64" in guion
    # Y compila también la fuente del lock de arranque
    assert "for fuente in requirements.txt requirements-bootstrap.txt" in guion
