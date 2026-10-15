"""
Tests de start_all_mappers (#565): la lista única de mappers.

Se ejecutan en un proceso limpio, porque la suite ya los ha arrancado al cargar
conftest: dentro de este proceso no se vería ni el primer arranque ni el segundo.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_starting_all_mappers_twice_is_harmless():
    """
    GIVEN: Un proceso limpio
    WHEN: Se arrancan todos los mappers dos veces seguidas
    THEN: La segunda no falla (son idempotentes) y quedan todas las tablas
    """
    result = _run(
        "from src.config.mappers import start_all_mappers\n"
        "from src.shared.infrastructure.persistence.sqlalchemy.base import metadata\n"
        "start_all_mappers()\n"
        "start_all_mappers()\n"
        "print('TABLES=' + str(len(metadata.tables)))\n"
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert "TABLES=35" in result.stdout
