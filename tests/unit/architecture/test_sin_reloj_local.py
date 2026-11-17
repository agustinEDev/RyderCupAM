"""
Ningún reloj local en el código (re-auditoría F-02, 17 nov 2026).

`datetime.now()` sin zona da la hora LOCAL de la máquina, y ruff solo la caza cuando se
llama (DTZ005). Pasada sin llamar, como reloj por defecto (`reloj=datetime.now`), se colaba:
en una máquina fuera de UTC chocaba con las fechas, que se guardan en UTC. Los relojes son
los de `src/shared/domain/services/instante_utc.py`, el único módulo que lee el reloj.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3] / "src"

# Cualquier `datetime.now` (con zona o sin ella, llamado o no) y `datetime.utcnow`: el reloj
# solo se lee en `instante_utc`
_RELOJ_LOCAL = re.compile(r"\bdatetime\.(?:now|utcnow)\b")


def test_el_codigo_no_lee_el_reloj_local():
    """
    Given: Todo el código de src
    When: Se busca `datetime.now` sin zona o `datetime.utcnow`, llamados o no
    Then: No aparece fuera de los comentarios ni fuera de instante_utc
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
