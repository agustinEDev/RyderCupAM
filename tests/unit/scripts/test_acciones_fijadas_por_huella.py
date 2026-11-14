"""
Toda acción de GitHub va fijada por la huella de su commit (auditoría de la fase 6,
INF-03, A08).

Una etiqueta (`@v7`) o una rama se pueden mover: quien controle esa acción cambiaría el
código que corre en el CI, que tiene secretos y permiso de escritura en algunos jobs. La
huella (40 caracteres hexadecimales) no se mueve. Al lado va un comentario con la
versión, para leerla; Dependabot actualiza las dos cosas.

    caso                                          | qué pasa
    ----------------------------------------------|---------------------------------
    P1/P3 cada `uses:` de cada workflow           | `dueño/acción@<huella>  # vX.Y.Z`
    una acción local (`./...`)                     | vale: es del propio repo
    el escáner                                     | reconoce etiqueta, rama y huella
"""

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[3] / ".github" / "workflows"
USES = re.compile(r"^\s*-?\s*uses:\s*(?P<accion>[^\s#]+)(?P<resto>.*)$")
FIJADA = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
VERSION = re.compile(r"#\s*v\d+(\.\d+)*")


def _mal_fijadas(texto: str) -> list[str]:
    """Las acciones de un workflow que no van por huella con su versión al lado."""
    malas = []
    for linea in texto.splitlines():
        encontrada = USES.match(linea)
        if not encontrada:
            continue
        accion = encontrada["accion"].strip("'\"")
        if accion.startswith("./"):
            continue
        if not FIJADA.match(accion) or not VERSION.search(encontrada["resto"]):
            malas.append(accion)
    return malas


def test_every_action_in_every_workflow_is_pinned_by_commit_with_its_version():
    ficheros = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert ficheros, "no se encontró ningún workflow"

    malas = {f.name: m for f in ficheros if (m := _mal_fijadas(f.read_text()))}

    assert malas == {}


def test_the_scanner_tells_a_tag_a_branch_and_a_pinned_commit_apart():
    huella = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    assert _mal_fijadas("      - uses: actions/checkout@v7") == ["actions/checkout@v7"]
    assert _mal_fijadas("        uses: actions/checkout@main") == ["actions/checkout@main"]
    assert _mal_fijadas(f"      - uses: actions/checkout@{huella}") == [
        f"actions/checkout@{huella}"
    ]
    assert _mal_fijadas(f"      - uses: actions/checkout@{huella}  # v7.0.1") == []
    assert _mal_fijadas(f"      - uses: github/codeql-action/upload-sarif@{huella} # v4.39.3") == []
    assert _mal_fijadas("      - uses: ./.github/actions/propia") == []
