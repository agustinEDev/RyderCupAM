"""
Toda acción de GitHub va fijada por la huella de su commit (auditoría de la fase 6,
INF-03, A08).

Una etiqueta (`@v7`) o una rama se pueden mover: quien controle esa acción cambiaría el
código que corre en el CI, que tiene secretos y permiso de escritura en algunos jobs. La
huella (40 caracteres hexadecimales) no se mueve. Al lado va un comentario con la
versión, para leerla; Dependabot actualiza las dos cosas.

Las acciones se sacan leyendo el YAML (cualquier forma de escribir un paso, también la
compacta `- {uses: ...}`); el comentario de la versión, de la línea donde aparece.

    caso                                                 | qué pasa
    -----------------------------------------------------|------------------------------
    A1 cada acción de cada workflow y acción compuesta   | `dueño/acción@<huella> # vX.Y`
    A2 una acción local (`./...`)                        | vale: es del propio repo
    A3 una imagen `docker://` por digest                 | vale
    A4 hay acciones que revisar                          | si no, pasaría en vacío
    A5 el escáner                                        | distingue etiqueta, rama y huella,
                                                         | y la forma compacta
    A6 dos ficheros con el mismo nombre                  | se revisan los dos
"""

import re
from pathlib import Path

import yaml

GITHUB = Path(__file__).resolve().parents[3] / ".github"
FIJADA = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
DOCKER_FIJADA = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-f]{64}$")
VERSION = re.compile(r"#\s*v\d+(\.\d+)*")


def _ficheros() -> list[Path]:
    """Los workflows y las acciones compuestas del repo."""
    return sorted([*GITHUB.glob("workflows/*.y*ml"), *GITHUB.glob("actions/**/action.y*ml")])


def _acciones(nodo: object) -> list[str]:
    """Todos los valores de `uses` del YAML, estén donde estén y se escriban como se escriban."""
    if isinstance(nodo, dict):
        propias = [str(v) for k, v in nodo.items() if k == "uses" and v is not None]
        return propias + [a for v in nodo.values() for a in _acciones(v)]
    if isinstance(nodo, list):
        return [a for v in nodo for a in _acciones(v)]
    return []


def _mal_fijadas(texto: str) -> list[str]:
    """Las acciones de un fichero que no van por huella con su versión al lado."""
    lineas = texto.splitlines()
    malas = []
    for accion in _acciones(yaml.safe_load(texto)):
        if accion.startswith("./") or DOCKER_FIJADA.match(accion):
            continue
        con_version = any(
            accion in linea and VERSION.search(linea.split(accion, 1)[1]) for linea in lineas
        )
        if not FIJADA.match(accion) or not con_version:
            malas.append(accion)
    return malas


def _revisa(textos: dict[str, str]) -> dict[str, list[str]]:
    """Las mal fijadas de cada fichero, por su ruta (dos con el mismo nombre no se pisan)."""
    return {ruta: m for ruta, texto in textos.items() if (m := _mal_fijadas(texto))}


def test_a1_every_action_is_pinned_by_commit_with_its_version():
    textos = {str(f.relative_to(GITHUB)): f.read_text() for f in _ficheros()}
    assert textos, "no se encontró ningún workflow"

    assert _revisa(textos) == {}


def test_a4_there_are_actions_to_check():
    """Si el escáner dejara de encontrar acciones, el test anterior pasaría en vacío."""
    assert sum(len(_acciones(yaml.safe_load(f.read_text()))) for f in _ficheros()) > 0


def test_a5_the_scanner_tells_a_tag_a_branch_and_a_pinned_commit_apart():
    huella = "3d3c42e5aac5ba805825da76410c181273ba90b1"

    def paso(linea: str) -> str:
        return f"jobs:\n  j:\n    steps:\n{linea}\n"

    assert _mal_fijadas(paso("      - uses: actions/checkout@v7")) == ["actions/checkout@v7"]
    assert _mal_fijadas(paso("      - uses: actions/checkout@main")) == ["actions/checkout@main"]
    assert _mal_fijadas(paso(f"      - uses: actions/checkout@{huella}")) == [
        f"actions/checkout@{huella}"
    ]
    assert _mal_fijadas(paso(f"      - uses: actions/checkout@{huella}  # v7.0.1")) == []
    assert _mal_fijadas(paso("      - uses: ./.github/actions/propia")) == []
    assert _mal_fijadas(paso(f"      - uses: docker://ghcr.io/x/y@sha256:{'a' * 64}")) == []
    assert _mal_fijadas(paso("      - uses: docker://ghcr.io/x/y:latest")) == [
        "docker://ghcr.io/x/y:latest"
    ]
    # La forma compacta de un paso (CodeRabbit)
    assert _mal_fijadas(paso("      - {name: Checkout, uses: actions/checkout@v7}")) == [
        "actions/checkout@v7"
    ]
    assert _mal_fijadas(paso("      - 'uses': actions/checkout@v7")) == ["actions/checkout@v7"]


def test_a6_two_files_with_the_same_name_are_both_checked():
    """CodeRabbit: dos `action.yml` en carpetas distintas no pueden pisarse."""
    mala = "runs:\n  steps:\n    - uses: actions/checkout@v7\n"
    buena = "runs:\n  steps:\n    - uses: ./.github/actions/otra\n"

    assert _revisa({"actions/a/action.yml": mala, "actions/b/action.yml": buena}) == {
        "actions/a/action.yml": ["actions/checkout@v7"]
    }
