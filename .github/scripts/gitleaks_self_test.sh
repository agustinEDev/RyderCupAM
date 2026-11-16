#!/usr/bin/env bash
# Autoprueba de gitleaks (INF-01, auditoría del 16 nov 2026): la config del repo TIENE
# que encontrar un secreto. Hasta entonces `.gitleaks.toml` no cargaba ninguna regla y
# el escaneo pasaba siempre en verde sin que nadie lo notara.
#
# Escribe tres secretos sintéticos en un fichero de src/ (fuera de la allowlist), pasa
# gitleaks con la config del repo y falla si no encuentra los tres. Los valores se
# derivan de un sha256 fijo, así que no hay azar (el mismo resultado en cada ejecución)
# y ninguno aparece literal en el repo: si estuvieran escritos aquí, el escaneo de los
# commits los marcaría.
#
# Uso: bash .github/scripts/gitleaks_self_test.sh   (desde la raíz, con gitleaks en el PATH)
set -euo pipefail

fixture="src/_gitleaks_self_test.py"
report="$(mktemp)"
trap 'rm -f "$fixture" "$report"' EXIT

python3 - "$fixture" <<'PY'
import hashlib
import sys

semilla = hashlib.sha256(b"rydercupam-gitleaks-self-test").digest() * 4


def de(alfabeto: str, n: int, desde: int) -> str:
    return "".join(alfabeto[b % len(alfabeto)] for b in semilla[desde : desde + n])


aws = "AKIA" + de("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", 16, 0)
github = "ghp" + "_" + de("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz0123456789", 36, 16)
generico = de("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", 40, 52)

with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(f'AWS_ACCESS_KEY_ID = "{aws}"\n')
    f.write(f'GITHUB_TOKEN = "{github}"\n')
    f.write(f'SECRET_KEY = "{generico}"\n')
PY

# Código de salida propio para «hay fugas» (3), distinto del de error (1): un fallo de
# gitleaks (config rota, binario que no arranca) no puede pasar por «encontró algo»
set +e
gitleaks dir "$fixture" --config .gitleaks.toml --no-banner --redact \
  --exit-code 3 --report-format json --report-path "$report"
codigo=$?
set -e

if [ "$codigo" -ne 3 ]; then
  echo "::error::gitleaks no encontró los secretos sintéticos con .gitleaks.toml (salida $codigo): la config no detecta nada"
  exit 1
fi

reglas="$(python3 -c 'import json, sys; print(" ".join(sorted({f["RuleID"] for f in json.load(open(sys.argv[1]))})))' "$report")"
esperadas="aws-access-token generic-api-key github-pat"
if [ "$reglas" != "$esperadas" ]; then
  echo "::error::gitleaks encontró [$reglas] y tenía que encontrar [$esperadas]"
  exit 1
fi

echo "✅ gitleaks detecta con .gitleaks.toml: $reglas"
