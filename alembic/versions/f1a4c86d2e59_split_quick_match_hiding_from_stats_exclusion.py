"""split quick match hiding from stats exclusion

Hasta ahora `hidden_by_participant_ids` hacia dos cosas a la vez: la partida
desaparecia del historial del usuario Y dejaba de contar en sus estadisticas.
Un unico boton —una papelera, sin aviso y sin vuelta atras desde la app— para
dos efectos distintos. Se separan (BE #242):

- `hidden_by_participant_ids` se queda como esta: fuera de mi lista, definitivo.
- `stats_excluded_by_participant_ids`, nueva: no cuenta en mis estadisticas,
  pero la partida se sigue viendo en la lista y la marca se puede quitar.

Las filas existentes se MIGRAN de la primera a la segunda, y no al reves.
Quien pulso aquella papelera no pudo pedir nada permanente: no habia aviso ni
manera de deshacerlo, y de hecho el caso que destapo esto fue un usuario que
oculto una partida y se quedo sin forma de recuperarla. Lo unico que aquella
accion queria con seguridad es que la partida no contara, que es exactamente
la marca nueva, y esa si es reversible. Dejarlas en la papelera nueva las
condenaria a no volver, por un clic que nunca dijo eso.

Consecuencia visible al desplegar: las partidas ocultadas hasta hoy reaparecen
en el historial, marcadas como que no cuentan. Sus estadisticas no cambian.

Revision ID: f1a4c86d2e59
Revises: d3c7a5f18e42
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a4c86d2e59"
down_revision = "d3c7a5f18e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Se crea con default de servidor para que las filas existentes queden con
    # lista vacia y la columna pueda ser NOT NULL desde el principio.
    op.add_column(
        "quick_matches",
        sa.Column(
            "stats_excluded_by_participant_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )

    # Traspaso: lo que estaba oculto pasa a "no cuenta", y deja de estar oculto.
    op.execute(
        """
        UPDATE quick_matches
        SET stats_excluded_by_participant_ids = hidden_by_participant_ids,
            hidden_by_participant_ids = '[]'::jsonb
        WHERE jsonb_array_length(hidden_by_participant_ids) > 0
        """
    )


def downgrade() -> None:
    # AVISO: esto no es simetrico, y no puede serlo. Al volver atras solo queda
    # una columna, asi que las partidas marcadas con el ojo despues del
    # despliegue —que el usuario dejo fuera de sus estadisticas contando con que
    # seguirian en su lista— pasan a estar OCULTAS, justo lo que esa marca
    # prometia que no pasaria. No hay forma de distinguirlas de las que ya
    # venian ocultas de antes: la informacion de cual era cual se pierde al
    # fusionar las dos marcas en una.
    #
    # Lo que si se conserva es A QUIEN afecta cada marca. Las dos listas se
    # UNEN, no se elige una: en una misma partida, A puede haberla ocultado y B
    # haberla dejado fuera de sus estadisticas, y quedarse solo con la de A
    # borraria la de B en silencio —su partida volveria a contar sin que el
    # hiciera nada—. Se deduplica porque un mismo participante puede estar en
    # las dos listas.
    op.execute(
        """
        UPDATE quick_matches
        SET hidden_by_participant_ids = (
            SELECT COALESCE(jsonb_agg(DISTINCT elemento), '[]'::jsonb)
            FROM jsonb_array_elements(
                hidden_by_participant_ids || stats_excluded_by_participant_ids
            ) AS elementos(elemento)
        )
        WHERE jsonb_array_length(stats_excluded_by_participant_ids) > 0
        """
    )
    op.drop_column("quick_matches", "stats_excluded_by_participant_ids")
