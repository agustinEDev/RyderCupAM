"""
Tests de la tarjeta de resumen de cada job del CI (.github/scripts/summary_card.py).

Cada job del pipeline explica en la página de resumen de la ejecución qué
comprueba y qué ha salido, sin abrir el log ni bajar artefactos. La tarjeta
nunca debe tumbar el job: es informativa.

    #   entrada                                    | resultado
    ----|------------------------------------------|----------------------------------
    C1  status success                            | título con ✅, sin «If it fails»
    C2  status failure con --if-fails             | título con ❌ y «If it fails»
    C3  status cancelled                          | ⏹️, sin «If it fails»
    C4  status skipped                            | ⏭️, sin «If it fails»
    C5  status desconocido                        | ❔
    C6  failure sin --if-fails                    | sin línea «If it fails»
    C7  ya había contenido en el fichero          | se añade detrás, no lo pisa
    C8  sin GITHUB_STEP_SUMMARY                   | la tarjeta sale por stdout
    C9  argumentos que faltan o sobran            | sale con 0, avisando
    C10 el fichero de resumen no se puede abrir   | sale con 0, avisando
    C11 como proceso, con argumentos rotos        | código de salida 0
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "summary_card.py"
_spec = importlib.util.spec_from_file_location("summary_card", _RUTA)
card = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(card)


def _args(status, if_fails=None):
    argv = [
        "--title",
        "🛡️ OWASP (Semgrep)",
        "--what",
        "Scans the code.",
        "--status",
        status,
        "--result",
        "0 findings.",
    ]
    if if_fails is not None:
        argv += ["--if-fails", if_fails]
    return argv


@pytest.fixture
def resumen(tmp_path, monkeypatch):
    ruta = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(ruta))
    return ruta


def test_c1_success_card(resumen):
    """
    GIVEN: Un job que ha salido bien
    WHEN: Se escribe su tarjeta
    THEN: El título lleva ✅ y salen «What it does» y «Result», sin «If it fails»
    """
    assert card.main(_args("success", if_fails="Run semgrep locally.")) == 0

    texto = resumen.read_text()
    assert "### 🛡️ OWASP (Semgrep) — ✅" in texto
    assert "**What it does:** Scans the code." in texto
    assert "**Result:** 0 findings." in texto
    assert "If it fails" not in texto


def test_c2_failure_card_explains_what_to_do(resumen):
    """
    GIVEN: Un job que ha fallado y un consejo para arreglarlo
    WHEN: Se escribe su tarjeta
    THEN: El título lleva ❌ y sale «If it fails» con el consejo
    """
    card.main(_args("failure", if_fails="Run semgrep locally."))

    texto = resumen.read_text()
    assert "### 🛡️ OWASP (Semgrep) — ❌" in texto
    assert "**If it fails:** Run semgrep locally." in texto


@pytest.mark.parametrize(("status", "emoji"), [("cancelled", "⏹️"), ("skipped", "⏭️")])
def test_c3_c4_cancelled_and_skipped(resumen, status, emoji):
    """
    GIVEN: Un job cancelado o saltado
    WHEN: Se escribe su tarjeta
    THEN: Lleva su emoji y no da consejos de arreglo
    """
    card.main(_args(status, if_fails="Run semgrep locally."))

    texto = resumen.read_text()
    assert f"— {emoji}" in texto
    assert "If it fails" not in texto


def test_c5_unknown_status(resumen):
    """
    GIVEN: Un estado que no es ninguno de los de GitHub
    WHEN: Se escribe su tarjeta
    THEN: Lleva ❔
    """
    card.main(_args("weird"))

    assert "### 🛡️ OWASP (Semgrep) — ❔" in resumen.read_text()


def test_c6_failure_without_advice(resumen):
    """
    GIVEN: Un job fallido sin --if-fails
    WHEN: Se escribe su tarjeta
    THEN: No sale la línea «If it fails»
    """
    card.main(_args("failure"))

    texto = resumen.read_text()
    assert "— ❌" in texto
    assert "If it fails" not in texto


def test_c7_appends_to_the_summary(resumen):
    """
    GIVEN: Un resumen que ya tiene contenido de otro paso
    WHEN: Se escribe la tarjeta
    THEN: El contenido anterior sigue y la tarjeta va detrás
    """
    resumen.write_text("## Previous section\n")

    card.main(_args("success"))

    texto = resumen.read_text()
    assert texto.startswith("## Previous section\n")
    assert texto.index("Previous section") < texto.index("OWASP")


def test_c8_without_summary_file_prints_to_stdout(monkeypatch, capsys):
    """
    GIVEN: Sin GITHUB_STEP_SUMMARY (en local)
    WHEN: Se escribe la tarjeta
    THEN: Sale por la salida estándar
    """
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert card.main(_args("success")) == 0
    assert "### 🛡️ OWASP (Semgrep) — ✅" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [[], ["--title", "x"], [*_args("success"), "--bogus"], ["--status"]],
    ids=["nothing", "missing", "unknown-flag", "flag-without-value"],
)
def test_c9_bad_arguments_never_fail(resumen, capsys, argv):
    """
    GIVEN: Argumentos que faltan, sobran o están rotos
    WHEN: Se llama a la tarjeta
    THEN: Devuelve 0 y avisa, sin lanzar
    """
    assert card.main(argv) == 0
    assert "warning" in capsys.readouterr().out.lower()


def test_c10_unwritable_summary_never_fails(tmp_path, monkeypatch, capsys):
    """
    GIVEN: Un GITHUB_STEP_SUMMARY que apunta a un sitio donde no se puede escribir
    WHEN: Se escribe la tarjeta
    THEN: Devuelve 0 y avisa
    """
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "no-such-dir" / "summary.md"))

    assert card.main(_args("success")) == 0
    assert "warning" in capsys.readouterr().out.lower()


def test_c11_the_process_exits_zero_with_bad_arguments(tmp_path):
    """
    GIVEN: El script ejecutado como proceso, como en el CI, sin argumentos
    WHEN: Termina
    THEN: Su código de salida es 0
    """
    proceso = subprocess.run(
        [sys.executable, str(_RUTA), "--nope"],
        env={"GITHUB_STEP_SUMMARY": str(tmp_path / "s.md"), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert proceso.returncode == 0
