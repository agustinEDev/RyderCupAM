"""replace enrollment_opens_at with enrollment_opens_days_before

Lo que el organizador dice son DIAS de antelacion, no una fecha y una hora
(BE #332). El instante deja de guardarse y se deriva de la fecha de inicio en
cada lectura, asi que mover el torneo mueve la apertura con el.

Sin conversion de datos, y a proposito por dos motivos. Produccion no tiene ni
una fila: `enrollment_opens_at` esta en develop pero nunca se desplego. Y una
migracion que LEE datos devuelve None en modo offline (`--sql`) y tumba el Build
Docker, que si bloquea; calcular los dias desde la fecha guardada obligaria a
leer `start_date` fila a fila y caeria justo en esa trampa.

Sin CHECK del rango 1-14: la regla vive en la entidad, la tabla `competitions`
no tiene ninguno, y cambiar manana el tope a 21 no deberia costar otra migracion.

Revision ID: a3f7d21c65b8
Revises: d7a1e94c38b2
Create Date: 2026-09-21

"""

import sqlalchemy as sa

from alembic import op

revision = "a3f7d21c65b8"
down_revision = "d7a1e94c38b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("competitions", "enrollment_opens_at")
    op.add_column(
        "competitions",
        sa.Column("enrollment_opens_days_before", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("competitions", "enrollment_opens_days_before")
    op.add_column(
        "competitions",
        sa.Column("enrollment_opens_at", sa.DateTime(), nullable=True),
    )
