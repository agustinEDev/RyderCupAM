"""
Tests del driver síncrono que usa Alembic (alembic/env.py).

El 1 oct 2026 la v2.23.0 no arrancó en Render: SQLAlchemy 2.1 cambió el driver
por defecto de `postgresql://` de psycopg2 a psycopg (v3), que no está
instalado, y la `DATABASE_URL` de Render no lleva driver. `env.py` solo
traducía `+asyncpg` a `+psycopg2`, así que `alembic upgrade head` del arranque
caía con «No module named 'psycopg'». Ni el CI ni el Kind lo vieron: sus URLs
llevan `+asyncpg`.

SQLAlchemy importa el driver al crear el motor, antes de conectarse, así que
basta con una URL a un puerto cerrado: con el driver bueno sale un error de
conexión; con el malo, el del módulo que falta.

    #   DATABASE_URL                       | Alembic usa
    ----|-----------------------------------|----------------------------
    D1  postgresql://… (la de Render)      | psycopg2: error de conexión
    D2  postgresql+asyncpg://… (CI, Kind)  | psycopg2: error de conexión
    D3  postgresql+psycopg2://…            | psycopg2, tal cual
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
# Un puerto en el que no escucha nadie: falla al conectar, nunca toca una BD
_DESTINO = "u:p@127.0.0.1:1/nada"


@pytest.mark.parametrize(
    "esquema",
    ["postgresql", "postgresql+asyncpg", "postgresql+psycopg2"],
    ids=["D1-sin-driver", "D2-asyncpg", "D3-psycopg2"],
)
def test_alembic_uses_psycopg2_whatever_the_url_says(esquema):
    """
    GIVEN: Una DATABASE_URL con ese esquema, a un puerto cerrado
    WHEN: Se ejecuta `alembic upgrade head` como en el arranque del contenedor
    THEN: Falla al CONECTAR con psycopg2, no por un driver que no está instalado
    """
    entorno = {**os.environ, "DATABASE_URL": f"{esquema}://{_DESTINO}"}

    proceso = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    salida = proceso.stdout + proceso.stderr

    assert "No module named 'psycopg'" not in salida, salida[-1500:]
    assert "psycopg2.OperationalError" in salida, salida[-1500:]
