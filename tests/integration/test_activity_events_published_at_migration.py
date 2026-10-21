"""
La migracion de `published_at` sobre una base de datos con eventos de antes.

Los tests construyen el esquema desde los mappers, asi que el relleno de una
migracion solo se puede comprobar aplicandola de verdad: base desechable,
`alembic upgrade` hasta la revision anterior, filas viejas, y luego el resto.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import DATABASE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ANTERIOR = "e7f9a1b3c5d7"
COLUMNAS = "a1f3c5e7b9d2"
INDICE = "b2e4d6f8a0c3"
NOMBRE_INDICE = "ix_activity_events_user_published"

JUGADO = datetime(2026, 9, 14, 0, 0)


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg", "postgresql+psycopg2").replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )


def _alembic(url: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"`alembic {' '.join(args)}` fallo:\n{result.stdout}\n{result.stderr}")


@pytest.fixture
def base_desechable():
    base_url = _sync_url(DATABASE_URL).rsplit("/", 1)[0]
    db_name = f"test_pubmig_{uuid.uuid4().hex[:8]}"
    admin = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    admin.dispose()
    try:
        yield f"{base_url}/{db_name}"
    finally:
        admin = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": db_name},
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        admin.dispose()


def _evento_viejo(url: str) -> str:
    """Un usuario y un logro suyo tal como estaban antes de la migracion."""
    user_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at) "
                "VALUES (:id, 'Ana', 'Garcia', :email, now(), now())"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(
            text(
                "INSERT INTO activity_events (id, user_id, type, occurred_at, source_match_id) "
                "VALUES (:id, :user_id, 'BIRDIE', :jugado, 'match-1')"
            ),
            {"id": event_id, "user_id": user_id, "jugado": JUGADO},
        )
    engine.dispose()
    return event_id


def _fila(url: str, event_id: str):
    engine = create_engine(url)
    with engine.connect() as conn:
        fila = conn.execute(
            text(
                "SELECT occurred_at, published_at, visible_to_friends "
                "FROM activity_events WHERE id = :id"
            ),
            {"id": event_id},
        ).one()
    engine.dispose()
    return fila


def _indice_valido(url: str) -> bool | None:
    engine = create_engine(url)
    with engine.connect() as conn:
        valido = conn.execute(
            text(
                "SELECT i.indisvalid FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid "
                "WHERE c.relname = :name"
            ),
            {"name": NOMBRE_INDICE},
        ).scalar()
    engine.dispose()
    return valido


def test_a7_rellena_published_at_con_occurred_at_en_las_filas_existentes(base_desechable):
    """
    A7. Given un logro de antes del cambio / When se migra / Then su
    `published_at` es su `occurred_at` y sigue visible para los amigos.

    Rellenar con la fecha de la migracion pondria todo el historial como
    recien publicado: el aviso contaria cosas de hace meses y el feed se
    desordenaria.
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    event_id = _evento_viejo(base_desechable)

    _alembic(base_desechable, "upgrade", INDICE)

    fila = _fila(base_desechable, event_id)
    assert fila.published_at == JUGADO
    assert fila.visible_to_friends is True
    assert _indice_valido(base_desechable) is True


def test_las_filas_nuevas_sin_fecha_toman_la_hora_utc_del_servidor(base_desechable):
    """
    Given el esquema migrado / When se inserta un evento sin `published_at`
    (codigo viejo durante el despliegue) / Then toma la hora actual en UTC y
    sin zona, como las que escribe la aplicacion.
    """
    _alembic(base_desechable, "upgrade", INDICE)
    event_id = _evento_viejo(base_desechable)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        ahora_utc = conn.execute(text("SELECT timezone('utc', now())")).scalar()
    engine.dispose()

    fila = _fila(base_desechable, event_id)
    assert abs((fila.published_at - ahora_utc).total_seconds()) < 60


def test_se_puede_bajar_y_volver_a_subir(base_desechable):
    """
    Given la base migrada / When se baja una y dos revisiones y se vuelve a
    subir / Then el indice se quita y se rehace, y los datos aguantan.
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    event_id = _evento_viejo(base_desechable)
    _alembic(base_desechable, "upgrade", INDICE)

    _alembic(base_desechable, "downgrade", COLUMNAS)
    assert _indice_valido(base_desechable) is None
    _alembic(base_desechable, "downgrade", ANTERIOR)
    _alembic(base_desechable, "upgrade", INDICE)

    assert _indice_valido(base_desechable) is True
    assert _fila(base_desechable, event_id).published_at == JUGADO
