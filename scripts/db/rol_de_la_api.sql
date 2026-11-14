-- El usuario de la API: solo filas, nunca estructura (auditoría de la fase 6, DB-01).
--
-- Lo ejecuta el DUEÑO de la base (el usuario con el que entran las migraciones), conectado
-- a la base de la app. Se puede repetir: no falla si ya está hecho. No lleva contraseña:
-- se pone aparte, a mano (en psql, `\password rydercup_app`), y no se guarda en ningún
-- fichero.
--
-- Después, en Render: DATABASE_URL con rydercup_app y MIGRATIONS_DATABASE_URL con la URL
-- de ahora (la del dueño). Guía: docs/RUNBOOK.md, «Usuario de la API sin permisos de estructura»

-- 1. El usuario, sin ningún poder sobre el servidor
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rydercup_app') THEN
        CREATE ROLE rydercup_app LOGIN
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
END
$$;

-- 2. Entrar en la base y ver el esquema (no crear en él)
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO rydercup_app', current_database());
END
$$;
GRANT USAGE ON SCHEMA public TO rydercup_app;
REVOKE CREATE ON SCHEMA public FROM rydercup_app;

-- 3. Las filas de las tablas de hoy, y las secuencias
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rydercup_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rydercup_app;

-- 4. Lo mismo en las tablas que creen las migraciones futuras (las crea el dueño, que es
--    quien ejecuta esto: ALTER DEFAULT PRIVILEGES vale para lo que cree el usuario actual)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rydercup_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO rydercup_app;

-- 5. La versión de las migraciones es solo del dueño
DO $$
BEGIN
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        REVOKE ALL ON public.alembic_version FROM rydercup_app;
    END IF;
END
$$;
