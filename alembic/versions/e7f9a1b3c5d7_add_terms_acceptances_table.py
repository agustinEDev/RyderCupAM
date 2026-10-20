"""Add terms_acceptances: history of Terms of use acceptances (20 oct 2026)

Decidido con Agustín el 20 oct 2026: además del estado actual en users
(terms_version y terms_accepted_at), cada aceptación real deja una fila con la
versión, cuándo, el email del usuario en ese momento, la IP y el navegador.
La fila sobrevive al borrado de la cuenta (ON DELETE SET NULL y
user_deleted_at) durante 3 años, y luego la purga la elimina
(scripts/purge_terms_acceptances.py). Una fila por usuario y versión.
Nace vacía: las aceptaciones de antes de esto no tienen historial. Solo SQL
plano: cabe en el guion del modo offline.

Revision ID: e7f9a1b3c5d7
Revises: d6e8f0a2b4c6
Create Date: 2026-10-20

"""

import sqlalchemy as sa
from alembic import op

revision = "e7f9a1b3c5d7"
down_revision = "d6e8f0a2b4c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea el historial, vacío, con su índice por usuario."""
    op.create_table(
        "terms_acceptances",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="NULL cuando la cuenta se borró (la fila se conserva como prueba)",
        ),
        sa.Column(
            "user_email",
            sa.String(255),
            nullable=False,
            comment="Email del usuario al aceptar: la prueba tras borrar la cuenta",
        ),
        sa.Column(
            "terms_version",
            sa.String(20),
            nullable=False,
            comment="Versión de los Términos aceptada",
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Cuándo la aceptó (UTC)",
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="IP del cliente según la API (NULL si no se pudo saber)",
        ),
        sa.Column(
            "user_agent",
            sa.String(500),
            nullable=True,
            comment="Navegador de la petición, recortado a 500 (NULL si no venía)",
        ),
        sa.Column(
            "user_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Cuándo se borró la cuenta (UTC); a los 3 años se purga la fila",
        ),
        sa.UniqueConstraint(
            "user_id", "terms_version", name="uq_terms_acceptances_user_version"
        ),
    )
    op.create_index("ix_terms_acceptances_user_id", "terms_acceptances", ["user_id"])
    op.create_index(
        "ix_terms_acceptances_user_deleted_at", "terms_acceptances", ["user_deleted_at"]
    )


def downgrade() -> None:
    """Borra el historial."""
    op.drop_index("ix_terms_acceptances_user_deleted_at", table_name="terms_acceptances")
    op.drop_index("ix_terms_acceptances_user_id", table_name="terms_acceptances")
    op.drop_table("terms_acceptances")
