"""competitions: the enrollment deadline (12:00 the day before), and scheduled opening from 2 days

Decidido por Agustín el 15 nov 2026: las inscripciones cierran solas a las 12:00 del
día anterior al torneo, a la hora del campo. Para eso la competición guarda:

- `enrollment_opened_at`: cuándo se abrieron o reabrieron por última vez (UTC). Abiertas
  a partir del plazo, el plazo no las cierra (R1, R2). Las ACTIVE de antes toman la hora
  de la migración: el cierre automático no cierra de golpe, en el primer despliegue, las
  que ya pasaron su plazo; siguen como hoy, hasta que las cierre el organizador.
- `enrollment_closed_by_deadline`: si las cerró el plazo y no el organizador (R3).
- `enrollment_close_blocked_notified`: si ya se le dijo al organizador que no se pueden
  cerrar solas (C4), para decírselo una vez y no cada hora.

Y la apertura programada pasa a ser de 2 a 14 días (A1): las que tenían 1, a 2.

Columnas con valor por defecto constante o vacías: en Postgres 11+ no reescriben la
tabla. Los UPDATE no leen nada, así que valen también para `upgrade --sql`. La release
anterior sigue funcionando con la tabla migrada (no las lee, y sus INSERT toman los
valores por defecto).

Revision ID: c8e1a3f5b7d9
Revises: f9b1d3e5a7c9
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "c8e1a3f5b7d9"
down_revision = "f9b1d3e5a7c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Si una transacción larga tuviera `competitions` bloqueada, mejor fallar a los 5 s
    # que dejar las competiciones en cola detrás del ALTER. SET LOCAL: solo aquí
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column(
        "competitions",
        sa.Column("enrollment_opened_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column(
            "enrollment_closed_by_deadline",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "competitions",
        sa.Column(
            "enrollment_close_blocked_notified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.execute(
        "UPDATE competitions SET enrollment_opened_at = (now() AT TIME ZONE 'UTC') "
        "WHERE status = 'ACTIVE'"
    )
    op.execute(
        "UPDATE competitions SET enrollment_opens_days_before = 2 "
        "WHERE enrollment_opens_days_before = 1"
    )


def downgrade() -> None:
    # Las que pasaron de 1 a 2 días se quedan en 2: no se sabe cuáles eran
    op.drop_column("competitions", "enrollment_close_blocked_notified")
    op.drop_column("competitions", "enrollment_closed_by_deadline")
    op.drop_column("competitions", "enrollment_opened_at")
