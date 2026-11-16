"""friendships: second_blocked_at, the block of the one who was already blocked (SB-02)

Decidido el 16 nov 2026, «bloqueo de los dos»: si B bloqueó a A y A bloquea a B, se
guardan los dos bloqueos en la misma fila (sigue habiendo una por pareja). El primero
sigue en `blocked_by`; esta columna dice cuándo bloqueó el otro participante. NULL es
lo de siempre: bloquea solo uno.

Compatibilidad: columna nullable y sin valor por defecto. En Postgres es un cambio de
metadatos, sin reescribir la tabla. No hay datos que migrar: todas las filas quedan a
NULL, que es exactamente lo que había. La release anterior sigue funcionando con la
tabla migrada: no la lee, y sus INSERT la dejan a NULL. Riesgo aceptado: mientras
convivan las dos versiones en el despliegue (segundos, hasta que Render retira la
instancia vieja), si el código nuevo guarda un segundo bloqueo y el viejo atiende un
desbloqueo de esa misma pareja, la fila se borra y se pierden los dos bloqueos. Al
migrar no hay ninguna fila con los dos, así que solo afecta a lo que pase en esa
ventana.

Downgrade: quita la columna. Una fila con los dos bloqueos se queda con el primero
(`blocked_by`, que es quien bloqueó antes): el código viejo no sabe representar dos. El
segundo bloqueador vuelve a lo de antes de esta release: el otro no existe para él
mientras dure el primer bloqueo, y si ese se quita, la fila se borra y él queda sin el
suyo. No hay filas a medias ni nada que el código viejo no entienda. Si una fila
quedó a nombre del segundo porque el primero desbloqueó, ya tiene la columna a NULL y
se queda tal cual: un bloqueo normal suyo.

Revision ID: e5a7c9b1d3f6
Revises: c8e1a3f5b7d9
Create Date: 2026-11-16

"""

import sqlalchemy as sa

from alembic import op

revision = "e5a7c9b1d3f6"
down_revision = "c8e1a3f5b7d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Si una transacción larga tuviera `friendships` bloqueada, mejor fallar a los 5 s
    # que dejar las amistades en cola detrás del ALTER. SET LOCAL: solo aquí
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("friendships", sa.Column("second_blocked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Las filas con los dos bloqueos se quedan con el primero (ver arriba)
    op.drop_column("friendships", "second_blocked_at")
