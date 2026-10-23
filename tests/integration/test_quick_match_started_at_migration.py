"""
La migración de `started_at` (f8a0c2e4b6d7) sobre partidas de antes: las que
ya estaban en juego toman su `updated_at`, que escribió el inicio (o algo
posterior), y no su `created_at`. Una partida creada el viernes y empezada el
domingo antes del despliegue se cerraba en la primera pasada (code-review).
"""

import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "e5f7a9b1c3d6"
STARTED_AT = "f8a0c2e4b6d7"

CREADA = datetime(2026, 10, 16, 18, 0)
EMPEZADA = datetime(2026, 10, 18, 8, 0)


def _partida(conn, user_id: str, course_id: str, status: str) -> str:
    match_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO quick_matches (id, creator_id, golf_course_id, match_format, status, "
            "participants, scorer_ids, hidden_by_participant_ids, "
            "stats_excluded_by_participant_ids, play_mode, created_at, updated_at) "
            "VALUES (:id, :u, :c, 'SINGLES', :s, '[]', '[]', '[]', '[]', 'HANDICAP', :cr, :up)"
        ),
        {"id": match_id, "u": user_id, "c": course_id, "s": status, "cr": CREADA, "up": EMPEZADA},
    )
    return match_id


def test_the_ones_in_progress_take_their_updated_at(base_desechable):  # noqa: F811
    _alembic(base_desechable, "upgrade", ANTERIOR)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        user_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at) "
                "VALUES (:id, 'Ana', 'Garcia', :email, now(), now())"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        course_id = conn.execute(text("SELECT id FROM golf_courses LIMIT 1")).scalar() or _campo(
            conn, user_id
        )
        en_juego = _partida(conn, user_id, course_id, "IN_PROGRESS")
        pendiente = _partida(conn, user_id, course_id, "PENDING")
        terminada = _partida(conn, user_id, course_id, "COMPLETED")
    engine.dispose()

    _alembic(base_desechable, "upgrade", STARTED_AT)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        filas = dict(conn.execute(text("SELECT id::text, started_at FROM quick_matches")).all())
    engine.dispose()
    assert filas[en_juego] == EMPEZADA
    assert filas[pendiente] is None
    assert filas[terminada] is None


def _campo(conn, user_id: str) -> str:
    course_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO golf_courses (id, name, country_code, course_type, creator_id, "
            "approval_status, created_at, updated_at) "
            "VALUES (:id, 'Meis', 'ES', 'STANDARD_18', :u, 'APPROVED', now(), now())"
        ),
        {"id": course_id, "u": user_id},
    )
    return course_id
