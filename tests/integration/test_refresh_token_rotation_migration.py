"""
La migración de la rotación del refresh token (F-02, caso A7) sobre tokens de antes.

  M1 al subir, los tokens que ya había siguen igual y quedan vigentes (columnas nulas):
     ninguna sesión cae al desplegar
  M2 bajar quita las columnas y deja los tokens
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, inspect, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "a2c4e6f8b0d1"
ROTACION = "b3d5f7a9c1e2"


def _token_de_antes(url: str) -> str:
    engine = create_engine(url)
    token_id = str(uuid.uuid4())
    with engine.begin() as conn:
        user_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at) "
                "VALUES (:id, 'Ana', 'Garcia', :email, now(), now())"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(
            text(
                "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at, "
                "revoked) VALUES (:id, :u, :h, :e, now(), false)"
            ),
            {
                "id": token_id,
                "u": user_id,
                "h": uuid.uuid4().hex * 2,
                "e": datetime.now() + timedelta(days=3),
            },
        )
    engine.dispose()
    return token_id


def test_m1_existing_tokens_stay_current_after_the_upgrade(base_desechable):  # noqa: F811
    _alembic(base_desechable, "upgrade", ANTERIOR)
    token_id = _token_de_antes(base_desechable)

    _alembic(base_desechable, "upgrade", ROTACION)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        fila = (
            conn.execute(
                text(
                    "SELECT revoked, replaced_at, replaced_by_id FROM refresh_tokens WHERE id = :id"
                ),
                {"id": token_id},
            )
            .mappings()
            .one()
        )
    engine.dispose()
    assert fila["revoked"] is False
    assert fila["replaced_at"] is None
    assert fila["replaced_by_id"] is None


def test_m2_the_downgrade_drops_the_columns_and_keeps_the_tokens(base_desechable):  # noqa: F811
    _alembic(base_desechable, "upgrade", ROTACION)
    token_id = _token_de_antes(base_desechable)

    _alembic(base_desechable, "downgrade", ANTERIOR)

    engine = create_engine(base_desechable)
    columnas = {c["name"] for c in inspect(engine).get_columns("refresh_tokens")}
    with engine.connect() as conn:
        quedan = conn.execute(
            text("SELECT count(*) FROM refresh_tokens WHERE id = :id"), {"id": token_id}
        ).scalar()
    engine.dispose()
    assert "replaced_at" not in columnas and "replaced_by_id" not in columnas
    assert quedan == 1
