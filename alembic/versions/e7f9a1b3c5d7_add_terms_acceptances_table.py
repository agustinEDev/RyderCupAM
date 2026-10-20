"""Add terms_acceptances: history of Terms of use acceptances (20 oct 2026)

Decidido con Agustín el 20 oct 2026: además del estado actual en users
(terms_version y terms_accepted_at), cada aceptación real deja una fila con la
versión, cuándo, el email del usuario en ese momento, la IP y el navegador.
La fila sobrevive al borrado de la cuenta (ON DELETE SET NULL, y un trigger
BEFORE DELETE ON users que rellena user_deleted_at) durante 3 años, y luego la purga la elimina
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
    """Crea el historial, vacío; el UNIQUE (user_id, terms_version) sirve de índice por usuario."""
    # Si una transacción larga (el vigilante de hándicaps) tuviera `users`
    # bloqueada, mejor fallar a los 5 s que dejar la app esperando detrás del
    # ALTER/CREATE TRIGGER: el contenedor no arranca y Render sigue con la versión
    # anterior. SET LOCAL: solo vale dentro de esta transacción.
    op.execute("SET LOCAL lock_timeout = '5s'")
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
    op.create_index(
        "ix_terms_acceptances_user_deleted_at", "terms_acceptances", ["user_deleted_at"]
    )
    # Al borrar un usuario por cualquier camino, sus aceptaciones se fechan
    # (la FK ya las desvincula con SET NULL): así la purga de los 3 años las
    # encuentra siempre. Copia de terms_acceptance_mapper.py
    op.execute(
        """
        CREATE OR REPLACE FUNCTION terms_acceptances_mark_user_deleted() RETURNS trigger AS $$
        BEGIN
            UPDATE terms_acceptances SET user_deleted_at = now()
            WHERE user_id = OLD.id AND user_deleted_at IS NULL;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_mark_terms_acceptances_deleted
        BEFORE DELETE ON users
        FOR EACH ROW EXECUTE FUNCTION terms_acceptances_mark_user_deleted()
        """
    )


def downgrade() -> None:
    """Borra el trigger, su función y el historial."""
    op.execute("DROP TRIGGER IF EXISTS trg_users_mark_terms_acceptances_deleted ON users")
    op.execute("DROP FUNCTION IF EXISTS terms_acceptances_mark_user_deleted()")
    op.drop_index("ix_terms_acceptances_user_deleted_at", table_name="terms_acceptances")
    op.drop_table("terms_acceptances")
