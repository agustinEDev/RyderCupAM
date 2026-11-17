"""
Ningún reloj local en el código (re-auditoría F-02, 17 nov 2026).

`datetime.now()` sin zona da la hora LOCAL de la máquina, y ruff solo la caza cuando se
llama (DTZ005). Pasada sin llamar, como reloj por defecto (`reloj=datetime.now`), se colaba:
en una máquina fuera de UTC chocaba con las fechas, que se guardan en UTC. Los relojes son
los de `src/shared/domain/services/instante_utc.py`.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3] / "src"

# `datetime.now` sin argumentos (llamado o no) y `datetime.utcnow`
_RELOJ_LOCAL = re.compile(r"\bdatetime\.(?:now\b(?!\(\s*(?:UTC|tz=|timezone\.utc))|utcnow\b)")


def test_el_codigo_no_lee_el_reloj_local():
    """
    Given: Todo el código de src
    When: Se busca `datetime.now` sin zona o `datetime.utcnow`, llamados o no
    Then: No aparece fuera de los comentarios
    """
    encontrados = []
    for fichero in RAIZ.rglob("*.py"):
        if fichero.name == "instante_utc.py":
            continue  # donde se definen los relojes; su texto lo explica
        for numero, linea in enumerate(fichero.read_text(encoding="utf-8").splitlines(), 1):
            codigo = linea.split("#", 1)[0]
            if _RELOJ_LOCAL.search(codigo):
                encontrados.append(f"{fichero.relative_to(RAIZ.parent)}:{numero}: {linea.strip()}")

    assert encontrados == [], "Reloj local; usar los de instante_utc:\n" + "\n".join(encontrados)
