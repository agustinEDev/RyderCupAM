"""hole_scores: cascade on users and dates without time zone, everywhere

Auditoría de la fase 6, DB-02. Producción tenía `hole_scores.player_user_id` sin borrado en
cascada y las fechas sin zona; la migración que creó la tabla (a3d5e7f1b2c4) declara
cascada y fechas con zona, y el mapeo del código, cascada y fechas sin zona. Decidido por
Agustín el 14 nov 2026: cascada (como el código y la migración) y fechas sin zona (como el
código y producción). Solo se cambia lo que difiere, así que vale para las dos:

- producción: la relación pasa a cascada; las fechas no se tocan;
- una base creada desde las migraciones: las fechas pasan a sin zona, en UTC (la API corre
  en UTC: la imagen no fija zona).

En producción la tabla está vacía (comprobado el 14 nov 2026, solo lectura).

Revision ID: e7b9d1f3a5c2
Revises: d4f6a8c0e2b5
Create Date: 2026-11-14

"""

from sqlalchemy import text

from alembic import op

revision = "e7b9d1f3a5c2"
down_revision = "d4f6a8c0e2b5"
branch_labels = None
depends_on = None

FK = "hole_scores_player_user_id_fkey"


def upgrade() -> None:
    conn = op.get_bind()
    # Como mucho 5 s esperando la tabla: si no, el arranque falla y Render sigue con la
    # versión anterior. SET LOCAL: solo en esta transacción
    op.execute("SET LOCAL lock_timeout = '5s'")

    borrado = conn.execute(
        text("SELECT confdeltype FROM pg_constraint WHERE conname = :n"), {"n": FK}
    ).scalar()
    if borrado != "c":
        op.execute(
            f"ALTER TABLE hole_scores DROP CONSTRAINT IF EXISTS {FK}, "
            f"ADD CONSTRAINT {FK} FOREIGN KEY (player_user_id) "
            "REFERENCES users(id) ON DELETE CASCADE"
        )

    for columna in ("created_at", "updated_at"):
        tipo = conn.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'hole_scores' AND column_name = :c"
            ),
            {"c": columna},
        ).scalar()
        if tipo == "timestamp with time zone":
            op.execute(
                f"ALTER TABLE hole_scores ALTER COLUMN {columna} "
                f"TYPE timestamp without time zone USING {columna} AT TIME ZONE 'UTC'"
            )


def downgrade() -> None:
    # Volver atrás reabriría la diferencia que esto cierra: no se deshace
    pass
