"""
La migración que alinea `hole_scores` (auditoría de la fase 6, DB-02).

Producción tiene la relación con `users` sin borrado en cascada y las fechas sin zona; la
migración que creó la tabla declara cascada y fechas con zona. Decidido el 14 nov 2026:
todas como producción (sin cascada, la base impide borrar a un usuario con golpes).
Venga de donde venga la base, tiene que quedar igual.

    caso                                         | después de migrar
    ---------------------------------------------|--------------------------------------
    H1 una base como producción                  | no cambia nada
    H2 una base creada desde las migraciones     | sin cascada; las fechas, sin zona
    H3 la relación con otro nombre               | se encuentra y se cambia igual
    H4 una fecha ya sin zona y la otra con zona  | solo cambia la que tiene zona; los
                                                 | valores no se mueven
"""

import uuid

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


def test_h1_a_database_like_production_is_left_as_it_is(
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

    assert _estado(base_desechable) == ("a", {"timestamp without time zone"})


def test_h2_a_database_built_from_migrations_ends_up_like_production(
    base_desechable,  # noqa: F811
):
    _alembic(base_desechable, "upgrade", ANTERIOR)
    assert _estado(base_desechable) == ("c", {"timestamp with time zone"})

    _alembic(base_desechable, "upgrade", ALINEA)

    assert _estado(base_desechable) == ("a", {"timestamp without time zone"})


def test_h3_the_relation_is_found_by_its_column_not_its_name(base_desechable):  # noqa: F811
    _alembic(base_desechable, "upgrade", ANTERIOR)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE hole_scores RENAME CONSTRAINT hole_scores_player_user_id_fkey "
                "TO fk_otro_nombre"
            )
        )
    engine.dispose()

    _alembic(base_desechable, "upgrade", ALINEA)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        borrados = (
            conn.execute(
                text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conrelid = 'hole_scores'::regclass AND contype = 'f' "
                    "AND conname = 'fk_otro_nombre'"
                )
            )
            .scalars()
            .all()
        )
    engine.dispose()
    assert borrados == ["a"]


def test_h4_only_the_column_with_time_zone_changes(base_desechable):  # noqa: F811
    """
    Una fecha ya sin zona y la otra con zona, con la base en hora de Madrid: si se
    convirtiera también la que no tiene zona, su valor se movería una hora (CodeRabbit).
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)
    engine = create_engine(base_desechable)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE hole_scores ALTER COLUMN created_at "
                "TYPE timestamp without time zone USING created_at AT TIME ZONE 'UTC'"
            )
        )
        # Por su nombre: `ALTER DATABASE CURRENT` es de Postgres 16 y el CI usa la 15
        nombre = conn.execute(text("SELECT current_database()")).scalar()
        conn.exec_driver_sql(f"ALTER DATABASE \"{nombre}\" SET TimeZone = 'Europe/Madrid'")
        # Un jugador de verdad (la migración vuelve a comprobar esa relación) y sin partido:
        # la clave del partido, apagada en esta sesión
        user_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at) "
                "VALUES (:id, 'Ana', 'Garcia', :email, now(), now())"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(
            text(
                "INSERT INTO hole_scores (id, match_id, hole_number, player_user_id, team, "
                "created_at, updated_at) VALUES (:id, :m, 1, :u, 'A', "
                "'2026-01-01 10:00:00', '2026-01-01 10:00:00+00')"
            ),
            {"id": str(uuid.uuid4()), "m": str(uuid.uuid4()), "u": user_id},
        )
    engine.dispose()

    _alembic(base_desechable, "upgrade", ALINEA)

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        fila = conn.execute(
            text("SELECT created_at::text, updated_at::text FROM hole_scores")
        ).one()
    engine.dispose()
    assert tuple(fila) == ("2026-01-01 10:00:00", "2026-01-01 10:00:00")
