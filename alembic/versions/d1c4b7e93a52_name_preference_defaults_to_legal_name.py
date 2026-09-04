"""name preference defaults to the legal name

La 4aeb1cb3223f dejó `use_real_name` en `false`: una competición seguía
mostrando el alias mientras nadie dijera lo contrario, que era el
comportamiento anterior a BE #254.

Se invierte por decisión de producto: una competición tiene lista de salida y
clasificación pública, y ahí lo normal es el nombre legal. El alias pasa a ser
lo que se pide a propósito, inscripción a inscripción.

Se arrastran TAMBIÉN las inscripciones que ya existen, no solo las nuevas: el
`server_default` a secas dejaría dos reglas conviviendo —las de antes con
alias, las de después con nombre legal— sin nada en la pantalla que explicara
la diferencia.

El downgrade devuelve el `server_default` y pone todo a `false`. Lo que NO
puede devolver es quién había elegido qué antes de este `UPDATE`: esa
información no está en ninguna parte una vez aplicado.

Revision ID: d1c4b7e93a52
Revises: 4aeb1cb3223f
Create Date: 2026-09-04

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d1c4b7e93a52"
down_revision = "4aeb1cb3223f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "enrollments",
        "use_real_name",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.true(),
    )
    op.execute("UPDATE enrollments SET use_real_name = true")


def downgrade() -> None:
    op.alter_column(
        "enrollments",
        "use_real_name",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.false(),
    )
    op.execute("UPDATE enrollments SET use_real_name = false")
