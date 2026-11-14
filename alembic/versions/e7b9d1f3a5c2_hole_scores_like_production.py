"""hole_scores: like production everywhere (no cascade on users, dates without time zone)

Auditoría de la fase 6, DB-02. La migración que creó la tabla (a3d5e7f1b2c4) declara
`player_user_id` con borrado en cascada y fechas con zona, pero producción tiene la
relación sin cascada y fechas sin zona. Decidido por Agustín el 14 nov 2026: todas como
producción. Sin cascada, la base impide borrar a un usuario con golpes anotados, también
en una carrera con quien anota en ese momento (borrarlos falsearía el resultado del
partido para sus rivales); las fechas sin zona son las que escribe el código.

Solo se cambia lo que difiere, así que en producción no hace nada; en una base creada
desde las migraciones quita la cascada y pasa las fechas a sin zona, en UTC (la API corre
en UTC: la imagen no fija zona).

Revision ID: e7b9d1f3a5c2
Revises: d4f6a8c0e2b5
Create Date: 2026-11-14

"""

from alembic import op

revision = "e7b9d1f3a5c2"
down_revision = "d4f6a8c0e2b5"
branch_labels = None
depends_on = None

# Un bloque DO: decide dentro de la base, así que vale también para `upgrade --sql` (el
# Build Docker del CI lo genera sin conexión). La relación se busca por tabla y columna,
# no por su nombre: si en alguna base se llamara distinto, se cambiaría igual (/code-review)
_ALINEA = """
DO $$
DECLARE
    fk record;
    columna text;
BEGIN
    FOR fk IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = 'public.hole_scores'::regclass
          AND c.contype = 'f'
          AND a.attname = 'player_user_id'
          AND c.confdeltype <> 'a'
    LOOP
        EXECUTE format(
            'ALTER TABLE public.hole_scores DROP CONSTRAINT %1$I, '
            'ADD CONSTRAINT %1$I FOREIGN KEY (player_user_id) REFERENCES public.users(id)',
            fk.conname
        );
    END LOOP;

    -- Cada columna por su tipo: una que ya esté sin zona no se toca (CodeRabbit)
    FOREACH columna IN ARRAY ARRAY['created_at', 'updated_at'] LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'hole_scores'
              AND column_name = columna
              AND data_type = 'timestamp with time zone'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.hole_scores ALTER COLUMN %1$I '
                'TYPE timestamp without time zone USING %1$I AT TIME ZONE ''UTC''',
                columna
            );
        END IF;
    END LOOP;
END
$$;
"""


def upgrade() -> None:
    op.execute(_ALINEA)


def downgrade() -> None:
    # Volver atrás reabriría la diferencia que esto cierra: no se deshace
    pass
