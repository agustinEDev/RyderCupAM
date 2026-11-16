-- Ajustes de la base que no son de una migración (re-auditoría del 16 nov 2026).
--
-- Aplicados en producción el 17 nov 2026 por Agustín, como el dueño de la base. Están
-- aquí para no perderlos: una base restaurada en limpio NO los trae (los ALTER ROLE
-- viven fuera de la base y pg_dump no los copia) y hay que volver a ejecutarlo. Guía:
-- docs/RUNBOOK.md, «Restaurar producción».
--
--   DB-04  Tiempos límite del usuario de la API a nivel de rol, los mismos que la API pone
--          en cada conexión (src/config/database.py), más la espera por un bloqueo, que la
--          API no fija: 10 s (decidido por Agustín el 17 nov 2026). Cubren a quien entre
--          como rydercup_app por otro camino. Los de n8n_lectura los pone rol_de_n8n.sql.
--   DB-06  Nadie crea tablas temporales salvo a quien se le dé (la app, la copia nocturna
--          y n8n no las usan; las migraciones corren como el dueño, que lo conserva).
--   (17 oct) Nadie crea objetos en el esquema public salvo el dueño (backup_ro creaba
--          tablas con el permiso viejo de PUBLIC).
--
-- Lo ejecuta el DUEÑO de la base, conectado a la base de la app, en psql y con
-- `\set ON_ERROR_STOP on` antes del `\i`. Se puede repetir: deja siempre el mismo estado.
-- Los ALTER ROLE valen para las conexiones nuevas: la API las va renovando sola.

BEGIN;

ALTER ROLE rydercup_app SET statement_timeout = '15s';
ALTER ROLE rydercup_app SET idle_in_transaction_session_timeout = '120s';
ALTER ROLE rydercup_app SET lock_timeout = '10s';

DO $$
BEGIN
    EXECUTE format('REVOKE TEMP ON DATABASE %I FROM PUBLIC', current_database());
END
$$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Comprobación antes del COMMIT: si algo no cuadra, no cambia nada
DO $$
DECLARE
    ajustes text[];
BEGIN
    SELECT s.setconfig INTO ajustes
    FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole
    WHERE r.rolname = 'rydercup_app' AND s.setdatabase = 0;
    IF NOT (ajustes @> ARRAY['statement_timeout=15s',
                             'idle_in_transaction_session_timeout=120s',
                             'lock_timeout=10s']) THEN
        RAISE EXCEPTION 'rydercup_app no tiene sus tiempos límite: %', ajustes;
    END IF;
    IF has_database_privilege('public', current_database(), 'TEMP') THEN
        RAISE EXCEPTION 'PUBLIC sigue pudiendo crear tablas temporales';
    END IF;
    IF has_schema_privilege('public', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'PUBLIC sigue pudiendo crear en el esquema public';
    END IF;
END
$$;

COMMIT;

-- Lo que tiene que salir: rydercup_app con los tres tiempos, y en datacl la primera
-- entrada «=c/…» (sin la T)
SELECT r.rolname, s.setconfig
FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole
WHERE r.rolname IN ('rydercup_app', 'n8n_lectura', 'backup_ro')
ORDER BY 1;
SELECT datacl FROM pg_database WHERE datname = current_database();
