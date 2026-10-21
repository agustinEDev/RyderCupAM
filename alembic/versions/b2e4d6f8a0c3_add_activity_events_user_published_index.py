"""add index on activity_events (user_id, published_at DESC, id DESC)

El feed se ordena ya por `published_at` y desempata por `id`, que es también su
cursor. El índice viejo (`ix_activity_events_user_occurred`) se queda de
momento: el código que se está retirando durante el despliegue todavía ordena
por `occurred_at`, y se borra en una PR posterior.

CONCURRENTLY para no bloquear escrituras mientras se construye, lo que obliga a
salir de la transacción de Alembic (`autocommit_block`). Y, como en
`43bc18ca6df1`, se borra antes un índice inválido que haya dejado un intento
anterior a medias: `IF NOT EXISTS` lo daría por bueno y el planificador lo
ignoraría.

Revision ID: b2e4d6f8a0c3
Revises: a1f3c5e7b9d2
Create Date: 2026-10-21

"""

import sqlalchemy as sa
from alembic import op

revision = "b2e4d6f8a0c3"
down_revision = "a1f3c5e7b9d2"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_activity_events_user_published"

_IS_INVALID = sa.text(
    """
    SELECT 1
    FROM pg_class c
    JOIN pg_index i ON i.indexrelid = c.oid
    WHERE c.relname = :name AND NOT i.indisvalid
    """
)


def upgrade() -> None:
    context = op.get_context()

    if context.as_sql:
        # Modo offline (`alembic upgrade --sql`, el del CI): no hay base que
        # consultar, así que se emite el DROP siempre. Es idempotente
        leftover_is_invalid = True
    else:
        # Fuera del autocommit_block: solo lee, y el bloque se queda con el DDL
        leftover_is_invalid = op.get_bind().execute(_IS_INVALID, {"name": INDEX_NAME}).scalar()

    with context.autocommit_block():
        if leftover_is_invalid:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON activity_events (user_id, published_at DESC, id DESC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
