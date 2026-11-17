"""
La migración del bloqueo de los dos (SB-02): una columna nullable y nada más.

Tiene que valer con el código viejo corriendo (no la lee, y sus INSERT la dejan
vacía), no reescribir `friendships` y colgar del head de develop.
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parents[3]
REVISION = "e5a7c9b1d3f6"


def _migracion():
    fichero = next((RAIZ / "alembic" / "versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("migracion_segundo_bloqueo", fichero)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_cuelga_del_head_de_develop_y_no_deja_dos_heads():
    """
    Given las migraciones / Then esta va tras c8e1a3f5b7d9, sigue en la cadena del único
    head (las que vengan después cuelgan de ella) y no hay dos heads.
    """
    scripts = ScriptDirectory.from_config(Config(str(RAIZ / "alembic.ini")))

    assert scripts.get_revision(REVISION).down_revision == "c8e1a3f5b7d9"
    heads = scripts.get_heads()
    assert len(heads) == 1
    cadena = {r.revision for r in scripts.iterate_revisions(heads[0], "base")}
    assert REVISION in cadena


def test_sube_una_columna_nullable_sin_valor_por_defecto(monkeypatch):
    """
    Given la migración / When sube
    Then solo añade `second_blocked_at` nullable y sin default: en Postgres es un
    cambio de metadatos, sin reescribir la tabla, y el código viejo no la ve
    """
    migracion = _migracion()
    op = MagicMock()
    monkeypatch.setattr(migracion, "op", op)

    migracion.upgrade()

    (tabla, columna), _ = op.add_column.call_args
    assert tabla == "friendships"
    assert columna.name == "second_blocked_at"
    assert columna.nullable is True
    assert columna.server_default is None
    assert isinstance(columna.type, sa.DateTime)
    assert not op.execute.call_args_list[1:], "nada de UPDATE: no hay datos que migrar"


def test_baja_quitando_la_columna(monkeypatch):
    """Given la migración / When baja / Then quita la columna (queda el primer bloqueo)."""
    migracion = _migracion()
    op = MagicMock()
    monkeypatch.setattr(migracion, "op", op)

    migracion.downgrade()

    op.drop_column.assert_called_once_with("friendships", "second_blocked_at")
