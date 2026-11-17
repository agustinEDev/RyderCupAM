"""
La migración del índice duplicado de refresh_tokens (DB-07): quita solo la restricción
que nadie usa y deja el índice único del mapper.
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic.config import Config
from alembic.script import ScriptDirectory

RAIZ = Path(__file__).resolve().parents[3]
REVISION = "b29a88392439"


def _migracion():
    fichero = next((RAIZ / "alembic" / "versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("migracion_indice_duplicado", fichero)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_hangs_from_the_second_block_and_leaves_one_head():
    """
    Given: Las migraciones
    When: Se mira dónde cuelga esta
    Then: Va tras e5a7c9b1d3f6 y sigue en la cadena del único head
    """
    scripts = ScriptDirectory.from_config(Config(str(RAIZ / "alembic.ini")))

    assert scripts.get_revision(REVISION).down_revision == "e5a7c9b1d3f6"
    heads = scripts.get_heads()
    assert len(heads) == 1
    assert REVISION in {r.revision for r in scripts.iterate_revisions(heads[0], "base")}


def test_upgrade_drops_only_the_unused_constraint(monkeypatch):
    """
    Given: La migración
    When: Sube
    Then: Quita la restricción `refresh_tokens_token_hash_key` (si existe) y nada más:
          el índice único `ix_refresh_tokens_token_hash`, el que se usa, se queda
    """
    modulo = _migracion()
    op = MagicMock()
    monkeypatch.setattr(modulo, "op", op)

    modulo.upgrade()

    sentencias = [c.args[0] for c in op.execute.call_args_list]
    assert sentencias == [
        "ALTER TABLE refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_token_hash_key"
    ]
    assert not op.drop_index.called


def test_downgrade_restores_the_constraint_with_its_name(monkeypatch):
    """
    Given: La migración
    When: Baja
    Then: Vuelve a crear la restricción única con el mismo nombre y columna
    """
    modulo = _migracion()
    op = MagicMock()
    monkeypatch.setattr(modulo, "op", op)

    modulo.downgrade()

    op.create_unique_constraint.assert_called_once_with(
        "refresh_tokens_token_hash_key", "refresh_tokens", ["token_hash"]
    )
