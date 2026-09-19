"""align max_players default with the domain

La columna `competitions.max_players` se creó con `server_default = 24`, un número
que ya no existe en ningún otro sitio: el dominio usa `DEFAULT_MAX_PLAYERS = 12`
(una Ryder entre amigos son 12 jugadores) y así lo declaran también el DTO y el
mapper (BE #312).

Hoy no muerde, porque la entidad siempre trae su propio valor y ningún INSERT deja
la columna fuera. Se corrige para que la base de datos deje de ser una tercera
versión de la verdad: cualquier inserción futura que omita la columna —SQL a mano,
una migración de datos— caería en 24 sin que nadie lo hubiera decidido.

Solo cambia el valor por defecto. Las filas existentes no se tocan: su cupo es un
dato que eligió su creador.

Revision ID: b4e91c72fa30
Revises: 9b2f4c81de07
Create Date: 2026-09-19

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b4e91c72fa30"
down_revision = "9b2f4c81de07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE competitions ALTER COLUMN max_players SET DEFAULT 12")


def downgrade() -> None:
    op.execute("ALTER TABLE competitions ALTER COLUMN max_players SET DEFAULT 24")
