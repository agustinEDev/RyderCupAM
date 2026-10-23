"""
La migracion de los apuntes de logros retirados (e5f7a9b1c3d6) sobre una base
con datos de la 2.38.0: los apuntes de entonces eran todos de logros ocultos, y
los eventos de antes tienen como escritura su fecha de publicacion.
"""

import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "d4e6f8a0b2c5"
APUNTES = "e5f7a9b1c3d6"

PUBLICADO = datetime(2026, 10, 22, 21, 30)


def _datos_de_la_2_38(url: str) -> str:
    """Un usuario, un logro publicado y un apunte de un logro oculto retirado."""
    user_id = str(uuid.uuid4())
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
                "INSERT INTO activity_events "
                "(id, user_id, type, occurred_at, published_at, source_match_id) "
                "VALUES (:id, :u, 'BIRDIE', :p, :p, 'grupo-1')"
            ),
            {"id": str(uuid.uuid4()), "u": user_id, "p": PUBLICADO},
        )
        conn.execute(
            text(
                "INSERT INTO withdrawn_hidden_achievements (user_id, source_match_id, type) "
                "VALUES (:u, 'grupo-2', 'NEW_COURSE')"
            ),
            {"u": user_id},
        )
    engine.dispose()
    return user_id


def _consulta(url: str, sql: str):
    engine = create_engine(url)
    with engine.connect() as conn:
        filas = conn.execute(text(sql)).all()
    engine.dispose()
    return filas


def test_the_notes_of_2_38_are_hidden_and_old_events_were_written_when_published(
    base_desechable,  # noqa: F811
):
    _alembic(base_desechable, "upgrade", ANTERIOR)
    _datos_de_la_2_38(base_desechable)

    _alembic(base_desechable, "upgrade", APUNTES)

    assert _consulta(
        base_desechable,
        "SELECT published_at, hidden, hidden_holes, golf_course_id "
        "FROM withdrawn_hidden_achievements",
    ) == [(None, True, None, None)]
    assert _consulta(base_desechable, "SELECT written_at FROM activity_events") == [(PUBLICADO,)]


def test_going_back_forgets_the_visible_notes(base_desechable):  # noqa: F811
    """El codigo de la 2.38.0 leeria como oculto todo apunte que quede."""
    _alembic(base_desechable, "upgrade", APUNTES)
    user_id = _datos_de_la_2_38(base_desechable)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO withdrawn_hidden_achievements "
                "(user_id, source_match_id, type, published_at, hidden) "
                "VALUES (:u, 'grupo-3', 'BIRDIE', :p, false)"
            ),
            {"u": user_id, "p": PUBLICADO},
        )
    engine.dispose()

    _alembic(base_desechable, "downgrade", ANTERIOR)

    assert _consulta(
        base_desechable, "SELECT source_match_id, type FROM withdrawn_hidden_achievements"
    ) == [("grupo-2", "NEW_COURSE")]
