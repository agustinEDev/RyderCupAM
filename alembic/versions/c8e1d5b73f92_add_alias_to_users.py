"""add alias to users

El alias es el apodo publico con el que la aplicacion pinta a una persona en
lugar de su nombre real (BE #239). Es opcional: sin alias se sigue enseñando
el nombre completo.

Es UNICO entre todos los usuarios ignorando mayusculas, que es una decision de
producto: dos cuentas llamadas «Chuchi» harian inutil el alias para encontrar
gente y trivial hacerse pasar por otro.

El indice es funcional —sobre LOWER(alias)— y parcial —solo donde hay alias—.
Lo segundo hace falta porque en Postgres los NULL no colisionan entre si en un
indice unico, pero un indice funcional sobre LOWER(NULL) tampoco aporta nada:
se deja fuera para que no ocupe ni se recorra.

No hay relleno de datos: las cuentas existentes se quedan con alias NULL, que
significa «usa mi nombre real».

Revision ID: c8e1d5b73f92
Revises: f1a4c86d2e59
Create Date: 2026-08-31

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c8e1d5b73f92"
down_revision = "f1a4c86d2e59"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("alias", sa.String(length=20), nullable=True))

    op.create_index(
        "ix_users_alias_lower",
        "users",
        [sa.text("LOWER(alias)")],
        unique=True,
        postgresql_where=sa.text("alias IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_alias_lower", table_name="users")
    op.drop_column("users", "alias")
