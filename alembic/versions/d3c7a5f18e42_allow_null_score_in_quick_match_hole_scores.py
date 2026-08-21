"""allow null score in quick_match_hole_scores

Un hoyo se puede dar por acabado sin haberlo acabado: el jugador recoge la bola.
En la tarjeta eso es una raya, y hasta ahora la partida rapida no tenia donde
guardarla — la columna era NOT NULL, asi que el frontend mandaba `score: null`,
Pydantic lo rechazaba y la pantalla ensenaba "Ese resultado no es valido".
El modulo de competicion ya lo admitia (`own_score: int | None`), asi que el
mismo boton funcionaba en un sitio y en el otro no.

La raya es un hoyo ANOTADO, no un hoyo pendiente: la diferencia entre `score`
nulo y no tener fila es justo esa, y de ella dependen la clasificacion en vivo
(un hoyo recogido son 0 puntos Stableford, no un hoyo que falta por jugar) y
poder dar la partida por terminada.

El CHECK `ck_quick_match_hole_score` no se toca: en SQL un CHECK sobre NULL
evalua a NULL y no se considera violado, asi que sigue acotando 1..15 los
scores que si son numero.

Revision ID: d3c7a5f18e42
Revises: b4d7e1a9c25f
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d3c7a5f18e42"
down_revision = "b4d7e1a9c25f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "quick_match_hole_scores",
        "score",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # Las rayas no caben en el esquema viejo. Volver atras las BORRA, y el hoyo
    # pasa de "recogido" a "sin anotar": es la unica lectura que el esquema
    # anterior sabe representar, y es preferible a que el downgrade reviente
    # contra el NOT NULL con la tabla ya poblada.
    op.execute("DELETE FROM quick_match_hole_scores WHERE score IS NULL")
    op.alter_column(
        "quick_match_hole_scores",
        "score",
        existing_type=sa.Integer(),
        nullable=False,
    )
