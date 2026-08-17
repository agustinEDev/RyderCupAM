"""add play_mode to quick_matches

Anade el modo de juego (SCRATCH / HANDICAP) a las partidas rapidas, el mismo
Value Object que ya usan las competiciones.

Las filas existentes NO se rellenan todas igual, y es deliberado: se les asigna
el modo que reproduce lo que la aplicacion venia mostrando, para no reescribir
el resultado de partidas ya jugadas.

- Match play YA TERMINADO o cancelado (match_format IS NOT NULL y status en
  COMPLETED/CANCELLED): el resultado se venia calculando con los golpes brutos,
  sin aplicar handicap. Eso es exactamente SCRATCH, asi que se quedan en SCRATCH
  y su resultado guardado no se mueve.
- Todo lo demas, HANDICAP. Esto incluye el partido libre (su clasificacion ya se
  calculaba neta) y, sobre todo, las partidas de match play que en el momento del
  despliegue esten PENDING o IN_PROGRESS: esas todavia se van a jugar, no hay
  resultado que preservar, y sus jugadores las montaron dando por hecho que
  habria handicap. Dejarlas en SCRATCH seria un cambio silencioso e irreversible,
  porque no existe ningun endpoint que cambie `play_mode` despues de crear.

Las partidas nuevas nacen en HANDICAP salvo que el creador elija scratch.

Revision ID: b4d7e1a9c25f
Revises: e7f2b3c9d418
Create Date: 2026-08-15

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b4d7e1a9c25f"
down_revision = "e7f2b3c9d418"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Se crea nullable para poder rellenar las filas existentes antes de exigir
    # el NOT NULL: una tabla con datos no admite una columna NOT NULL sin default.
    op.add_column("quick_matches", sa.Column("play_mode", sa.String(20), nullable=True))

    op.execute(
        """
        UPDATE quick_matches
        SET play_mode = CASE
            WHEN match_format IS NOT NULL
                 AND status IN ('COMPLETED', 'CANCELLED') THEN 'SCRATCH'
            ELSE 'HANDICAP'
        END
        WHERE play_mode IS NULL
        """
    )

    op.alter_column(
        "quick_matches",
        "play_mode",
        nullable=False,
        server_default="HANDICAP",
    )

    op.create_check_constraint(
        "ck_quick_matches_play_mode",
        "quick_matches",
        "play_mode IN ('SCRATCH', 'HANDICAP')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_quick_matches_play_mode", "quick_matches", type_="check")
    op.drop_column("quick_matches", "play_mode")
