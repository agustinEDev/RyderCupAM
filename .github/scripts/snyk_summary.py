"""Resume los informes JSON de Snyk para la revisión periódica (semanal y en cada release).

Uso: python snyk_summary.py [--known FICHERO] <etiqueta>=<informe.json> [...]

Entiende los dos formatos del CLI: el de `snyk test` / `snyk container test`
(lista `vulnerabilities`) y el SARIF de `snyk code test`.

Escribe un resumen en Markdown por la salida estándar y deja en GITHUB_OUTPUT:
- `actionable`: avisos ALTOS o CRÍTICOS que piden acción. En dependencias e
  imagen, los que tienen arreglo: lo que Debian aún no ha parcheado se lista
  pero no pide nada, o la issue estaría siempre abierta. En el código, los de
  nivel alto que no estén en la lista de falsos positivos conocidos.
- `incomplete`: `true` si algún análisis no dio resultado (cuota, token, red).

La lista de conocidos (`--known`) es un JSON con entradas
{"rule": ..., "path": ..., "reason": ...}: cada falso positivo revisado a
mano, con su motivo, para que no reabra la issue cada quincena.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

SEVERIDADES = ["critical", "high", "medium", "low"]
# SARIF no tiene "critical": error = alto, warning = medio, note = bajo
NIVEL_SARIF = {"error": "high", "warning": "medium", "note": "low"}


def cargar(ruta: str) -> list[dict]:
    try:
        with Path(ruta).open(encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [{"error": f"no se pudo leer el informe: {e}"}]
    return datos if isinstance(datos, list) else [datos]


def tiene_arreglo(v: dict) -> bool:
    # Dependencias: isUpgradable/isPatchable. Contenedores: fixedIn.
    return bool(v.get("fixedIn") or v.get("isUpgradable") or v.get("isPatchable"))


def resumir_dependencias(inf: dict, etiqueta: str) -> tuple[list[str], int]:
    # Un aviso por identificador: el mismo fallo aparece una vez por cada ruta
    unicos = list({v["id"]: v for v in inf.get("vulnerabilities", [])}.values())
    cuenta = Counter(v["severity"] for v in unicos)
    objetivo = inf.get("displayTargetFile") or inf.get("path") or etiqueta
    lineas = [f"`{objetivo}`: " + " · ".join(f"{cuenta.get(s, 0)} {s}" for s in SEVERIDADES), ""]
    accionables = 0
    graves = [v for v in unicos if v["severity"] in ("critical", "high")]
    for v in sorted(graves, key=lambda v: SEVERIDADES.index(v["severity"])):
        arreglo = ", ".join(v.get("fixedIn") or []) or ("sí" if tiene_arreglo(v) else "no")
        lineas.append(
            f"- **{v['severity']}** `{v['packageName']}@{v.get('version')}`: "
            f"{v.get('title', '')[:80]} ({v['id']}) · arreglo: {arreglo}"
        )
        accionables += tiene_arreglo(v)
    return lineas + ([""] if graves else []), accionables


def resumir_codigo(inf: dict, conocidos: list[dict]) -> tuple[list[str], int]:
    resultados = inf["runs"][0].get("results", [])
    cuenta = Counter(NIVEL_SARIF.get(r.get("level"), "low") for r in resultados)
    lineas = ["Código: " + " · ".join(f"{cuenta.get(s, 0)} {s}" for s in SEVERIDADES), ""]
    accionables = 0
    for r in resultados:
        if NIVEL_SARIF.get(r.get("level")) != "high":
            continue
        loc = r["locations"][0]["physicalLocation"]
        ruta = loc["artifactLocation"]["uri"]
        linea = loc.get("region", {}).get("startLine")
        motivo = next(
            (k["reason"] for k in conocidos if k["rule"] == r["ruleId"] and k["path"] == ruta), None
        )
        marca = f" · *conocido, no pide acción: {motivo}*" if motivo else ""
        lineas.append(f"- **high** `{r['ruleId']}` en `{ruta}:{linea}`{marca}")
        accionables += motivo is None
    return [*lineas, ""], accionables


def main(args: list[str]) -> int:
    conocidos: list[dict] = []
    if args[:1] == ["--known"]:
        with Path(args[1]).open(encoding="utf-8") as f:
            conocidos = json.load(f)
        args = args[2:]

    salida = ["## Revisión de Snyk", ""]
    total = 0
    incompleto = False
    for arg in args:
        etiqueta, _, ruta = arg.partition("=")
        salida += [f"### {etiqueta}", ""]
        for inf in cargar(ruta):
            # un SARIF sin "runs" tampoco es un resultado
            if inf.get("error") or not (inf.get("runs") or "vulnerabilities" in inf):
                # Cuota agotada, token, red...: se dice, no se da por limpio
                incompleto = True
                salida += [f"⚠️ **Sin resultado**: {str(inf.get('error') or inf)[:300]}", ""]
                continue
            lineas, n = (
                resumir_codigo(inf, conocidos)
                if "runs" in inf
                else resumir_dependencias(inf, etiqueta)
            )
            salida += lineas
            total += n
    salida.append(f"**Altos o críticos que piden acción: {total}**")
    print("\n".join(salida))
    if gh := os.environ.get("GITHUB_OUTPUT"):
        with Path(gh).open("a", encoding="utf-8") as f:
            f.write(f"actionable={total}\nincomplete={'true' if incompleto else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
