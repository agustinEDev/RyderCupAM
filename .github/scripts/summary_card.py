"""Tarjeta de resumen de un job del CI, en la página de la ejecución.

Cada job del pipeline termina con una tarjeta que dice qué comprueba y qué ha
salido, para entenderlo sin abrir el log ni bajar artefactos:

    ### 🛡️ OWASP (Semgrep) — ✅
    **What it does:** ...
    **Result:** ...
    **If it fails:** ...      (solo si el job falló)

Uso:
    summary_card.py --title T --what W --status S --result R [--if-fails F]

Escribe al final de $GITHUB_STEP_SUMMARY (o por stdout, si no está). Es
informativa: SIEMPRE sale con 0, también con argumentos rotos (avisa).
"""

import argparse
import os
import sys
from pathlib import Path

_EMOJI = {"success": "✅", "failure": "❌", "cancelled": "⏹️", "skipped": "⏭️"}


class _Parser(argparse.ArgumentParser):
    """argparse que lanza en vez de salir del proceso."""

    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        raise ValueError(message or f"exit {status}")


def _parser() -> _Parser:
    parser = _Parser(add_help=False)
    parser.add_argument("--title", required=True)
    parser.add_argument("--what", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--if-fails", dest="if_fails", default="")
    return parser


def render(title: str, what: str, status: str, result: str, if_fails: str = "") -> str:
    status = status.strip().lower()
    lines = [
        f"### {title} — {_EMOJI.get(status, '❔')}",
        "",
        f"**What it does:** {what}",
        "",
        f"**Result:** {result}",
    ]
    if status == "failure" and if_fails:
        lines += ["", f"**If it fails:** {if_fails}"]
    return "\n".join(lines) + "\n\n"


def main(argv=None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        texto = render(args.title, args.what, args.status, args.result, args.if_fails)
        destino = os.environ.get("GITHUB_STEP_SUMMARY")
        if destino:
            with Path(destino).open("a", encoding="utf-8") as fichero:
                fichero.write(texto)
        else:
            print(texto, end="")
    except Exception as error:  # la tarjeta nunca tumba el job
        print(f"::warning::Summary card not written: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
