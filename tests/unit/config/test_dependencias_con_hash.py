"""
La imagen se instala desde `requirements.lock`, con un hash por paquete (OWASP A08,
F-18 de la auditoría del 9 nov 2026): si alguien sustituye un paquete en el índice,
pip se niega a instalarlo. El lock se genera desde `requirements.txt`, así que los
dos tienen que decir lo mismo; si no, la imagen instalaría otra versión de la que
se probó.
"""

import re
from pathlib import Path

import yaml

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


def test_the_dev_compose_gives_logs_its_own_named_volume():
    """
    Given: docker/docker-compose.yml, que monta el checkout entero sobre /app
    When: se mira cómo monta /app/logs
    Then: con un volumen con nombre declarado: el checkout del equipo no es escribible
          por el usuario 10001 de la imagen, y el log de seguridad se perdería
          (CodeRabbit en BE #774)
    """
    import yaml

    compose = yaml.safe_load((RAIZ / "docker" / "docker-compose.yml").read_text(encoding="utf-8"))
    montajes = compose["services"]["app"]["volumes"]
    de_logs = [m for m in montajes if str(m).endswith(":/app/logs")]

    assert len(de_logs) == 1
    volumen = de_logs[0].split(":")[0]
    assert not volumen.startswith((".", "/"))  # con nombre, no un directorio del equipo
    assert volumen in (compose.get("volumes") or {})


def _ordenes_del_dockerfile() -> list[str]:
    """Las instrucciones del Dockerfile, sin comentarios y con las continuaciones unidas."""
    texto = (RAIZ / "docker" / "Dockerfile").read_text(encoding="utf-8")
    sin_comentarios = [x for x in texto.splitlines() if not x.lstrip().startswith("#")]
    return [
        o.strip() for o in "\n".join(sin_comentarios).replace("\\\n", " ").splitlines() if o.strip()
    ]


def test_copy_tree_unreadable_by_others_is_made_readable_before_user():
    """
    Given: el Dockerfile, que copia el árbol tal como está en el equipo que construye
    When: se miran sus instrucciones (no los comentarios) antes del USER sin privilegios
    Then: un RUN da lectura a todos sobre /app, porque un checkout local con carpetas
          700 dejaba al uid 10001 sin poder importar el código (el Kind no arrancaba:
          ModuleNotFoundError al migrar, 9 nov 2026)
    """
    ordenes = _ordenes_del_dockerfile()
    usuario = next(i for i, o in enumerate(ordenes) if o.startswith("USER app"))
    # Después del ÚLTIMO COPY: lo que se copiara detrás conservaría los permisos del
    # equipo y el usuario podría volver a no leerlo
    ultimo_copy = max(i for i, o in enumerate(ordenes) if o.startswith("COPY"))
    antes = ordenes[ultimo_copy + 1 : usuario]

    assert any(
        o.startswith("RUN") and re.search(r"find /app\b.*-exec chmod a\+rX", o) for o in antes
    )


def test_entrypoint_copied_with_600_gets_755_for_bash():
    """
    Given: el Dockerfile, que copia entrypoint.sh fuera de /app
    When: se miran sus instrucciones
    Then: 755 explícito. `chmod +x` conserva los bits de lectura del equipo: con un
          checkout en 600 quedaba en 711, y bash, que tiene que leer el script, no
          podía con el usuario sin privilegios
    """
    ordenes = _ordenes_del_dockerfile()

    assert "RUN chmod 755 /entrypoint.sh" in ordenes
    assert not any("chmod +x /entrypoint.sh" in o for o in ordenes)


def test_dockerignore_allows_only_runtime_files_and_drops_nested_caches():
    """
    Given: .dockerignore
    When: se lee
    Then: es una lista de PERMITIDOS (todo fuera y solo vuelve lo que la app usa en
          ejecución), sin volver a meter nada local, y las cachés se excluyen a
          cualquier profundidad, no solo en la raíz
    """
    lineas = [
        linea.strip()
        for linea in (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    ]
    vuelven = {linea[1:] for linea in lineas if linea.startswith("!")}

    assert lineas[0] == "*"
    assert vuelven == {
        "src",
        "alembic",
        "alembic.ini",
        "main.py",
        "entrypoint.sh",
        "scripts",
        "requirements.txt",
        "requirements.lock",
        "requirements-bootstrap.txt",
        "requirements-bootstrap.lock",
    }
    for patron in ("**/__pycache__", "**/*.py[cod]", "**/*.log", "**/.DS_Store"):
        assert patron in lineas, patron


def _destinos_del_checkout_en_la_app() -> list[tuple[str, str]]:
    """(origen, destino) de cada volumen del servicio app, en sintaxis corta o larga."""
    compose = yaml.safe_load((RAIZ / "docker" / "docker-compose.yml").read_text(encoding="utf-8"))
    montajes = []
    for volumen in compose["services"]["app"].get("volumes", []):
        if isinstance(volumen, str):
            partes = volumen.split(":")
            montajes.append((partes[0], partes[1] if len(partes) > 1 else ""))
        else:
            montajes.append((str(volumen.get("source", "")), str(volumen.get("target", ""))))
    return montajes


def test_dev_compose_mounts_only_the_code_not_the_whole_checkout():
    """
    Given: el compose de desarrollo, que monta el código para el hot-reload
    When: se leen los volúmenes del servicio app (sintaxis corta y larga)
    Then: ninguno monta la raíz del checkout (con él, el usuario de la app leía .env
          y los secretos locales del Kind) y el código entra por carpetas, no por
          ficheros sueltos (un fichero montado deja de verse cuando el editor lo
          sustituye por uno nuevo y el hot-reload se pierde)
    """
    montajes = _destinos_del_checkout_en_la_app()
    raices = {"..", "../", "./..", "../."}

    assert not [m for m in montajes if m[0].rstrip("/") in {r.rstrip("/") for r in raices}]
    assert ("../src", "/app/src") in montajes
    del_checkout = [m for m in montajes if m[0].startswith("..")]
    assert all((RAIZ / m[0].removeprefix("../")).is_dir() for m in del_checkout), del_checkout
