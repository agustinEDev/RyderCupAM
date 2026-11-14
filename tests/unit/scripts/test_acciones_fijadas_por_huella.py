"""
Toda acción de GitHub va fijada por la huella de su commit (auditoría de la fase 6,
INF-03, A08).

Una etiqueta (`@v7`) o una rama se pueden mover: quien controle esa acción cambiaría el
código que corre en el CI, que tiene secretos y permiso de escritura en algunos jobs. La
huella (40 caracteres hexadecimales) no se mueve. Al lado va un comentario con la
versión, para leerla; Dependabot actualiza las dos cosas.

    caso                                                 | qué pasa
    -----------------------------------------------------|------------------------------
    A1 cada `uses:` de cada workflow y acción compuesta  | `dueño/acción@<huella> # vX.Y`
    A2 una acción local (`./...`)                        | vale: es del propio repo
    A3 una imagen `docker://` por digest                 | vale
    A4 toda línea con `uses:` la reconoce el escáner      | si no, se le escaparía
    A5 el escáner                                        | distingue etiqueta, rama y huella
"""

import re
from pathlib import Path

GITHUB = Path(__file__).resolve().parents[3] / ".github"
USES = re.compile(r"^\s*-?\s*uses:\s*(?P<accion>[^\s#]+)(?P<resto>.*)$")
FIJADA = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
DOCKER_FIJADA = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-f]{64}$")
VERSION = re.compile(r"#\s*v\d+(\.\d+)*")


def _ficheros() -> list[Path]:
    """Los workflows y las acciones compuestas del repo."""
    return sorted([*GITHUB.glob("workflows/*.y*ml"), *GITHUB.glob("actions/**/action.y*ml")])


def _mal_fijadas(texto: str) -> list[str]:
    """Las acciones de un fichero que no van por huella con su versión al lado."""
    malas = []
    for linea in texto.splitlines():
        encontrada = USES.match(linea)
        if not encontrada:
            continue
        accion = encontrada["accion"].strip("'\"")
        if accion.startswith("./") or DOCKER_FIJADA.match(accion):
            continue
        if not FIJADA.match(accion) or not VERSION.search(encontrada["resto"]):
            malas.append(accion)
    return malas


def test_a1_every_action_is_pinned_by_commit_with_its_version():
    textos = {f.name: f.read_text() for f in _ficheros()}
    assert textos, "no se encontró ningún workflow"

    malas = {nombre: m for nombre, texto in textos.items() if (m := _mal_fijadas(texto))}

    assert malas == {}


def test_a4_the_scanner_recognises_every_line_that_uses_an_action():
    """Si una forma nueva de escribir `uses:` no casara, el test anterior no la vería."""
    sin_reconocer = [
        f"{f.name}: {linea.strip()}"
        for f in _ficheros()
        for linea in f.read_text().splitlines()
        if re.match(r"^\s*-?\s*uses:", linea) and not USES.match(linea)
    ]
    usos = [linea for f in _ficheros() for linea in f.read_text().splitlines() if USES.match(linea)]

    assert usos
    assert sin_reconocer == []


def test_a5_the_scanner_tells_a_tag_a_branch_and_a_pinned_commit_apart():
    huella = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert _mal_fijadas("      - uses: actions/checkout@v7") == ["actions/checkout@v7"]
    assert _mal_fijadas("        uses: actions/checkout@main") == ["actions/checkout@main"]
    assert _mal_fijadas(f"      - uses: actions/checkout@{huella}") == [
        f"actions/checkout@{huella}"
    ]
    assert _mal_fijadas(f"      - uses: actions/checkout@{huella}  # v7.0.1") == []
    assert _mal_fijadas(f"      - uses: github/codeql-action/upload-sarif@{huella} # v4.39.3") == []
    assert _mal_fijadas("      - uses: ./.github/actions/propia") == []
    assert _mal_fijadas(f"      - uses: docker://ghcr.io/x/y@sha256:{'a' * 64}") == []
    assert _mal_fijadas("      - uses: docker://ghcr.io/x/y:latest") == [
        "docker://ghcr.io/x/y:latest"
    ]
