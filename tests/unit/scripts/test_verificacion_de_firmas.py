"""
El script de firmas no se salta ningún commit (auditoría de la fase 6, INF-06).

`scripts/verify-gpg-signatures.sh` daba por buenos, sin mirarlos, los commits de merge y
los que tenían `noreply@github.com` como correo de committer. Los dos se pueden fabricar
en local sin firmar: `GIT_COMMITTER_EMAIL=noreply@github.com git commit` o un `git merge`
sin `-S`. Ahora a esos se les pregunta a GitHub si están verificados (los que hace
GitHub los firma él), y sin respuesta no hay aprobado.

Un repo git de prueba, con una clave GPG desechable y un `gh` falso: sin red ni la clave
de nadie.

    caso                                               | qué pasa
    ---------------------------------------------------|----------------------------------
    F1 un commit normal firmado                        | pasa (GPG local, como siempre)
    F2 sin firmar con committer noreply@github.com     | falla
    F3 un merge sin firmar hecho en local              | falla
    F4 un merge que GitHub da por verificado           | pasa
    F5 no se puede preguntar a GitHub                  | falla, con su mensaje
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "verify-gpg-signatures.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("gpg") is None or shutil.which("git") is None, reason="hace falta gpg y git"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def entorno(tmp_path: Path):
    """Un GNUPGHOME con una clave sin contraseña, un `gh` falso y un repo con un commit."""
    # En una ruta corta: el socket del agente de GPG no cabe en la de tmp_path
    gnupg = Path(tempfile.mkdtemp(prefix="g", dir="/tmp"))
    gnupg.chmod(0o700)
    env = {
        **os.environ,
        "GNUPGHOME": str(gnupg),
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GITHUB_REPOSITORY": "dueno/repo",
        "GPG_PUBLIC_KEY": "",
    }
    subprocess.run(
        [
            "gpg",
            "--batch",
            "--passphrase",
            "",
            "--quick-gen-key",
            "Prueba <prueba@x.test>",
            "ed25519",
            "sign",
            "never",
        ],
        env=env,
        check=True,
        capture_output=True,
    )
    clave = subprocess.run(
        ["gpg", "--list-secret-keys", "--with-colons"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    huella = next(linea.split(":")[9] for linea in clave.splitlines() if linea.startswith("fpr"))

    bin_falso = tmp_path / "bin"
    bin_falso.mkdir()
    (bin_falso / "gh").write_text(
        "#!/bin/sh\n"
        'echo "$@" >> "$GH_LLAMADAS"\n'
        'case "$GH_VERIFICADO" in fallo) exit 1 ;; *) echo "$GH_VERIFICADO" ;; esac\n'
    )
    (bin_falso / "gh").chmod(0o755)
    env.update(
        PATH=f"{bin_falso}:{env['PATH']}",
        GH_LLAMADAS=str(tmp_path / "llamadas.txt"),
        GH_VERIFICADO="false",
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main", env=env)
    for clave_cfg, valor in (
        ("user.name", "Prueba"),
        ("user.email", "prueba@x.test"),
        ("user.signingkey", huella),
        ("commit.gpgsign", "false"),
    ):
        _git(repo, "config", clave_cfg, valor, env=env)
    (repo / "a.txt").write_text("a")
    _git(repo, "add", ".", env=env)
    _git(repo, "commit", "-q", "-S", "-m", "base", env=env)
    yield {"repo": repo, "env": env, "base": _git(repo, "rev-parse", "HEAD", env=env)}
    subprocess.run(["gpgconf", "--kill", "gpg-agent"], check=False, env=env, capture_output=True)
    shutil.rmtree(gnupg, ignore_errors=True)


def _verifica(e: dict, **env_extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), e["base"], "HEAD"],
        check=False,
        cwd=e["repo"],
        env={**e["env"], **env_extra},
        capture_output=True,
        text=True,
    )


def _commit(e: dict, nombre: str, *flags: str, env_extra: dict | None = None) -> None:
    (e["repo"] / f"{nombre}.txt").write_text(nombre)
    _git(e["repo"], "add", ".", env=e["env"])
    _git(e["repo"], "commit", "-q", *flags, "-m", nombre, env={**e["env"], **(env_extra or {})})


def _merge_sin_firmar(e: dict) -> None:
    repo, env = e["repo"], e["env"]
    _git(repo, "checkout", "-q", "-b", "rama", env=env)
    _commit(e, "en-la-rama", "-S")
    _git(repo, "checkout", "-q", "main", env=env)
    _commit(e, "en-main", "-S")
    _git(repo, "merge", "-q", "--no-ff", "--no-gpg-sign", "-m", "merge", "rama", env=env)


def test_f1_a_signed_commit_passes(entorno):
    _commit(entorno, "firmado", "-S")

    resultado = _verifica(entorno)

    assert resultado.returncode == 0, resultado.stdout


def test_f2_an_unsigned_commit_with_a_forged_github_committer_fails(entorno):
    _commit(
        entorno,
        "falsificado",
        env_extra={"GIT_COMMITTER_EMAIL": "noreply@github.com", "GIT_COMMITTER_NAME": "GitHub"},
    )

    resultado = _verifica(entorno)

    assert resultado.returncode == 1, resultado.stdout


def test_f3_an_unsigned_local_merge_fails(entorno):
    _merge_sin_firmar(entorno)

    resultado = _verifica(entorno)

    assert resultado.returncode == 1, resultado.stdout


def test_f4_a_merge_that_github_verifies_passes(entorno):
    _merge_sin_firmar(entorno)

    resultado = _verifica(entorno, GH_VERIFICADO="true")

    assert resultado.returncode == 0, resultado.stdout
    merge = _git(entorno["repo"], "rev-parse", "HEAD", env=entorno["env"])
    assert f"repos/dueno/repo/commits/{merge}" in Path(entorno["env"]["GH_LLAMADAS"]).read_text()


def test_f5_without_an_answer_from_github_it_fails(entorno):
    _merge_sin_firmar(entorno)

    resultado = _verifica(entorno, GH_VERIFICADO="fallo")

    assert resultado.returncode == 1, resultado.stdout
    assert "GitHub" in resultado.stdout
