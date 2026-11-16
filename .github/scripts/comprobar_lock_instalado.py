"""
Comprueba que el entorno del CI tiene exactamente las versiones de requirements.lock.

El CI instala el lock con --require-hashes y encima las herramientas de desarrollo
(requirements-dev.txt). Si una de ellas pidiera otra versión de un paquete del lock, pip
la cambiaría sin avisar y los tests ya no probarían lo que se despliega (INF-05, re-auditoría
del 16 nov 2026). Sale con 1 y nombra cada paquete movido.

Uso: python .github/scripts/comprobar_lock_instalado.py [ruta del lock]
"""

import importlib.metadata
import re
import sys
from pathlib import Path

PIN = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;\\]+)", re.MULTILINE)


def _normaliza(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).lower()


def distintos(lock: Path) -> dict[str, tuple[str, str | None]]:
    """Paquete → (versión del lock, versión instalada o None) de cada uno que no coincide."""
    fijados = {_normaliza(n): v for n, v in PIN.findall(lock.read_text(encoding="utf-8"))}
    instalados = {
        _normaliza(d.metadata["Name"]): d.version for d in importlib.metadata.distributions()
    }
    return {n: (v, instalados.get(n)) for n, v in fijados.items() if instalados.get(n) != v}


def main() -> int:
    lock = Path(sys.argv[1] if len(sys.argv) > 1 else "requirements.lock")
    malos = distintos(lock)
    if malos:
        for nombre, (fijada, instalada) in sorted(malos.items()):
            print(f"::error::{nombre}: lock {fijada}, instalado {instalada}")
        print(
            f"{len(malos)} paquetes no coinciden con {lock}: el CI no probaría lo que se despliega"
        )
        return 1
    print(f"Las versiones instaladas coinciden con {lock}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
