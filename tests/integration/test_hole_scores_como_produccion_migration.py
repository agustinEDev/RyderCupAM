"""
La migración que alinea `hole_scores` (auditoría de la fase 6, DB-02).

Producción tenía la relación con `users` sin borrado en cascada y las fechas sin zona; la
migración que creó la tabla declara cascada y fechas con zona, y el mapeo del código,
cascada y fechas sin zona. Decidido el 14 nov 2026: cascada (como el código y la
migración) y fechas sin zona (como el código y producción). Venga de donde venga la base,
tiene que quedar igual.

    caso                                         | después de migrar
    ---------------------------------------------|--------------------------------------
    H1 una base como producción                  | cascada; las fechas siguen sin zona
    H2 una base creada desde las migraciones     | cascada; las fechas, sin zona
"""

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "d4f6a8c0e2b5"
ALINEA = "e7b9d1f3a5c2"


def _estado(url: str) -> tuple[str, set[str]]:
    engine = create_engine(url)
    with engine.connect() as conn:
        borrado = conn.execute(
            text(
                "SELECT confdeltype FROM pg_constraint "
                "WHERE conname = 'hole_scores_player_user_id_fkey'"
            )
        ).scalar()
        tipos = {
            fila[0]
            for fila in conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = 'hole_scores' AND column_name IN ('created_at', 'updated_at')"
                )
            )
        }
    engine.dispose()
    return borrado, tipos


def test_h1_a_database_like_production_gets_the_cascade_and_keeps_its_dates(
    base_desechable,  # noqa: F811
):
    _alembic(base_desechable, "upgrade", ANTERIOR)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE hole_scores DROP CONSTRAINT hole_scores_player_user_id_fkey, "
                "ADD CONSTRAINT hole_scores_player_user_id_fkey FOREIGN KEY (player_user_id) "
                "REFERENCES users(id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE hole_scores "
                "ALTER COLUMN created_at TYPE timestamp without time zone, "
                "ALTER COLUMN updated_at TYPE timestamp without time zone"
            )
        )
    engine.dispose()
    assert _estado(base_desechable) == ("a", {"timestamp without time zone"})

    _alembic(base_desechable, "upgrade", ALINEA)

    assert _estado(base_desechable) == ("c", {"timestamp without time zone"})


def test_h2_a_database_built_from_migrations_ends_up_like_production(
    base_desechable,  # noqa: F811
):
    _alembic(base_desechable, "upgrade", ANTERIOR)
    assert _estado(base_desechable) == ("c", {"timestamp with time zone"})

    _alembic(base_desechable, "upgrade", ALINEA)

    assert _estado(base_desechable) == ("c", {"timestamp without time zone"})
