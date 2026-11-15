"""Add handicap_update_emails: the RFEG update emails already sent (D2, 16 nov 2026)

Decidido con Agustín el 16 nov 2026: al jugador español al que la RFEG no
encuentra le llega UN correo por competición, la primera vez; las
actualizaciones siguientes (el botón del organizador o una programada) solo
renuevan su aviso de Actividad y el panel. Al organizador no se le vuelve a
mandar el mismo correo si su lista no cambió: se guarda la huella de la lista
enviada. Una fila por competición, destinatario y tipo de correo.

Nace vacía: los correos de antes no se apuntaron. Solo SQL plano: cabe en el
guion del modo offline.

Revision ID: f9b1d3e5a7c9
Revises: e7b9d1f3a5c2
Create Date: 2026-11-16

"""

import sqlalchemy as sa
from alembic import op

revision = "f9b1d3e5a7c9"
down_revision = "e7b9d1f3a5c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla, vacía; la clave (competición, usuario, tipo) es su índice."""
    # Si una transacción larga (el vigilante de hándicaps) tuviera bloqueadas
    # `competitions` o `users`, mejor fallar a los 5 s que dejar la app esperando
    # detrás de las claves ajenas. SET LOCAL: solo vale dentro de esta transacción.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "handicap_update_emails",
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            comment="A quién se envió: el jugador no encontrado o el organizador",
        ),
        sa.Column(
            "kind",
            sa.String(20),
            primary_key=True,
            comment="PLAYER_NOT_FOUND u ORGANIZER_LIST",
        ),
        sa.Column(
            "fingerprint",
            sa.String(64),
            nullable=False,
            comment="Huella (SHA-256) de la lista enviada al organizador; vacía para el jugador",
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Cuándo se envió (UTC)",
        ),
    )


def downgrade() -> None:
    """Quita la tabla: la versión anterior no la conoce."""
    op.drop_table("handicap_update_emails")
