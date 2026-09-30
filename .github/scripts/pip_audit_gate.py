"""
Puerta de pip-audit del CI: decide si el informe bloquea la PR.

Bloquea cualquier vulnerabilidad que tenga versión con arreglo, sea cual sea su
identificador. Hasta el 30 sep 2026 solo contaban los que empezaban por «CVE»,
y pip-audit usa sobre todo PYSEC- y GHSA-: con jinja2==3.1.2, cinco con
arreglo, contaba cero. Las que no tienen arreglo se enseñan, sin bloquear.

Un informe ausente o roto no es un aprobado: sale con 2.

Uso: python .github/scripts/pip_audit_gate.py pip-audit-report.json
Salidas: 0 aprobado · 1 vulnerabilidades con arreglo · 2 no se pudo comprobar
"""

import json
import os
import sys
from pathlib import Path

OK, VULNERABLE, SIN_COMPROBAR = 0, 1, 2


def _leer(ruta: Path) -> list[dict] | None:
    try:
        informe = json.loads(ruta.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"::error::No se puede leer el informe de pip-audit ({ruta}): {error}")
        return None
    dependencias = informe.get("dependencies") if isinstance(informe, dict) else None
    if not isinstance(dependencias, list):
        print(f"::error::El informe de pip-audit no tiene la lista 'dependencies' ({ruta})")
        return None
    return dependencias


def _escribir_salidas(total: int, con_arreglo: int, sin_arreglo: int) -> None:
    destino = os.environ.get("GITHUB_OUTPUT")
    if not destino:
        return
    with Path(destino).open("a", encoding="utf-8") as salida:
        salida.write(f"total_vulnerabilities={total}\n")
        salida.write(f"fixable_vulnerabilities={con_arreglo}\n")
        salida.write(f"unfixable_vulnerabilities={sin_arreglo}\n")


def main(argv: list[str]) -> int:
    ruta = Path(argv[0]) if argv else Path("pip-audit-report.json")
    dependencias = _leer(ruta)
    if dependencias is None:
        return SIN_COMPROBAR

    con_arreglo, sin_arreglo = [], []
    for dep in dependencias:
        # Un paquete que pip-audit no pudo mirar trae skip_reason y no trae vulns
        for vuln in dep.get("vulns") or []:
            linea = f"{dep.get('name')} {dep.get('version')}: {vuln.get('id')}"
            arreglos = vuln.get("fix_versions") or []
            if arreglos:
                con_arreglo.append(f"{linea} -> {', '.join(arreglos)}")
            else:
                sin_arreglo.append(linea)

    _escribir_salidas(len(con_arreglo) + len(sin_arreglo), len(con_arreglo), len(sin_arreglo))

    for linea in sin_arreglo:
        print(f"::warning::Sin arreglo todavía: {linea}")
    if con_arreglo:
        for linea in con_arreglo:
            print(f"::error::Vulnerabilidad con arreglo: {linea}")
        print(
            f"{len(con_arreglo)} con arreglo: subir esas versiones en requirements.txt o "
            "requirements-dev.txt. Si es pip o una dependencia indirecta, fijarla ahí o subir "
            "el paquete que la trae."
        )
        return VULNERABLE

    print(f"Sin vulnerabilidades con arreglo ({len(sin_arreglo)} sin arreglo, solo aviso).")
    return OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
