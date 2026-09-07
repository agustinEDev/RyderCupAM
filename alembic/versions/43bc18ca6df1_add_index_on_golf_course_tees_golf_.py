"""add index on golf_course_tees.golf_course_id

`golf_course_tees` se lleva la mayor parte del I/O de la base de datos: medido en
producción el 7 sep 2026, **36 millones de tuplas leídas secuencialmente** en 31.071
escaneos completos, sobre una tabla de 4.321 filas. Para comparar, `golf_course_tee_holes`
es 18 veces más grande y se lee casi siempre por índice.

La causa no se ve leyendo los modelos: la tabla YA tiene dos índices que empiezan por
`golf_course_id`, pero los dos son **parciales**

    uq_golf_course_tees_color_gender       ... WHERE (color <> 'OTHER')
    uq_golf_course_tees_identifier_gender  ... WHERE (color = 'OTHER')

y Postgres solo usa un índice parcial cuando puede demostrar que la consulta implica su
predicado. Un `WHERE golf_course_id = ?` no implica ninguno de los dos, así que el
planificador se queda sin índice utilizable y recorre la tabla entera. Los dos parciales
se quedan como están: cumplen su función de unicidad, y lo que falta es el simple.

CONCURRENTLY para no bloquear escrituras mientras se construye, lo que obliga a salir de
la transacción de Alembic (`autocommit_block`).

**Por qué se borra antes de crear.** Un CREATE INDEX CONCURRENTLY que muere a medias
—el contenedor que se lleva por delante el despliegue, un timeout, la conexión que se
cae— deja el índice creado pero con `indisvalid = false`, y el planificador ignora un
índice inválido. Como `entrypoint.sh` reintenta `alembic upgrade head` en cada arranque,
un simple `IF NOT EXISTS` vería el nombre ocupado, no haría nada, y Alembic marcaría la
revisión como aplicada: `alembic current` diría que está arreglado mientras la tabla se
sigue escaneando entera. Por eso se comprueba `indisvalid` y se borra el inválido antes
de reintentar.

Revision ID: 43bc18ca6df1
Revises: d1c4b7e93a52
Create Date: 2026-09-07

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "43bc18ca6df1"
down_revision = "d1c4b7e93a52"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_golf_course_tees_golf_course_id"

_IS_INVALID = sa.text(
    """
    SELECT 1
    FROM pg_class c
    JOIN pg_index i ON i.indexrelid = c.oid
    WHERE c.relname = :name AND NOT i.indisvalid
    """
)


def upgrade() -> None:
    # La comprobación va FUERA del autocommit_block, en la transacción de Alembic: solo
    # lee, y así el bloque de abajo se queda con el DDL que no puede ir en transacción.
    leftover_is_invalid = op.get_bind().execute(_IS_INVALID, {"name": INDEX_NAME}).scalar()

    with op.get_context().autocommit_block():
        if leftover_is_invalid:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON golf_course_tees (golf_course_id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
