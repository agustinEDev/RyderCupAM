#!/usr/bin/env bash
# Instala en el CI lo mismo que la imagen de producción (INF-05, re-auditoría del 16 nov
# 2026): pip desde requirements-bootstrap.lock y el proyecto desde requirements.lock, los
# dos con --require-hashes. Con --dev, encima, las herramientas de requirements-dev.txt.
# Al final comprueba que ninguna versión de los dos locks se ha movido: si una herramienta
# pidiera otra versión de un paquete del lock (o de pip), pip la cambiaría sin avisar y el
# CI ya no probaría lo que se despliega.
#
# No se usa `-c requirements.lock` con las herramientas: un lock con hashes como
# restricción pone a pip en modo --require-hashes y exige hash también a ellas.
#
# Uso: bash .github/scripts/instalar_dependencias.sh [--dev]   (desde la raíz)
set -euo pipefail

python -m pip install --require-hashes --no-deps -r requirements-bootstrap.lock
python -m pip install --require-hashes -r requirements.lock
if [ "${1:-}" = "--dev" ]; then
  python -m pip install -r requirements-dev.txt
fi
python .github/scripts/comprobar_lock_instalado.py requirements.lock requirements-bootstrap.lock
