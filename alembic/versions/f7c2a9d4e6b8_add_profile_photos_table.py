"""add profile_photos table

Revision ID: f7c2a9d4e6b8
Revises: d4e8f1a3b7c9
Create Date: 2026-08-11

Galeria de fotos del perfil (BE #177).

Las imagenes se guardan en la base de datos, como los avatares. A 1080 px y
calidad 85 cada foto pesa unos 375 KB, con tope de 10 por perfil: unos 3,7 MB
por jugador. Postgres guarda los `BYTEA` grandes comprimidos en una tabla
auxiliar (TOAST), asi que su peso no penaliza a ninguna consulta que no pida la
columna `image_data` — y el listado de la galeria no la pide.

Senal acordada para mover las imagenes fuera de la base de datos: cuando esta
tabla pase de 2 GB o el backup tarde mas de un par de minutos. Migrar entonces
es mover bytes y cambiar de donde se leen, no rehacer la funcionalidad.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f7c2a9d4e6b8"
down_revision = "d4e8f1a3b7c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_photos",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.CHAR(36), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("caption", sa.String(280), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    # La galeria siempre se pide igual: las fotos de este jugador, de la mas
    # reciente a la mas antigua
    op.create_index(
        "ix_profile_photos_user_created",
        "profile_photos",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_profile_photos_user_created", table_name="profile_photos")
    op.drop_table("profile_photos")
