"""refresh_tokens: drop the duplicate unique constraint on token_hash (DB-07)

La migración que creó la tabla (217417e0f20f) declaró la columna con `unique=True` y
además el índice único `ix_refresh_tokens_token_hash`: Postgres quedó con dos índices
únicos sobre la misma columna. El mapper declara `unique=True, index=True`, que en
SQLAlchemy es solo el índice único `ix_…`; la restricción `refresh_tokens_token_hash_key`
no la conoce nadie. En PRO (16 nov 2026, solo lectura): `ix_refresh_tokens_token_hash`
con 3 238 lecturas, `refresh_tokens_token_hash_key` con 0. Cada login y cada renovación
de sesión escribían en los dos.

Se quita la restricción. La unicidad sigue garantizada por el índice único, que es el
que usan las búsquedas. Un `ALTER TABLE … DROP CONSTRAINT` toma un bloqueo exclusivo
(no hay versión CONCURRENTLY para una restricción): espera a que acaben las
transacciones que tocan la tabla, que son de milisegundos (renovar sesión, entrar), y
mientras espera, los logins y renovaciones nuevos esperan detrás. Si en 5 s no lo
consigue, el `lock_timeout` de las migraciones (`alembic/env.py`) la aborta, la guardia
del arranque para el despliegue y la versión anterior sigue sirviendo: se vuelve a
desplegar. Riesgo aceptado: como mucho 5 s de espera en el login durante el despliegue.

Compatibilidad: la release anterior no nombra la restricción en ningún sitio; sus
INSERT siguen fallando con un duplicado igual que antes, por el índice único.

Downgrade: la vuelve a crear con el mismo nombre (falla si mientras tanto hubiera
duplicados, que el índice único impide).

Revision ID: b29a88392439
Revises: e5a7c9b1d3f6
Create Date: 2026-11-17

"""

from alembic import op

revision = "b29a88392439"
down_revision = "e5a7c9b1d3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_token_hash_key")


def downgrade() -> None:
    op.create_unique_constraint("refresh_tokens_token_hash_key", "refresh_tokens", ["token_hash"])
