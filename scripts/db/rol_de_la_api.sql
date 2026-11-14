-- El usuario de la API: solo filas, nunca estructura (auditoría de la fase 6, DB-01).
--
-- Lo ejecuta el DUEÑO de la base (el usuario con el que entran las migraciones), conectado
-- a la base de la app. Se puede repetir: no falla si ya está hecho. No lleva contraseña:
-- se pone aparte, a mano (en psql, `\password rydercup_app`), y no se guarda en ningún
-- fichero.
--
-- Después, en Render: DATABASE_URL con rydercup_app y MIGRATIONS_DATABASE_URL con la URL
-- de ahora (la del dueño). Guía: docs/RUNBOOK.md, «Usuario de la API sin permisos de estructura»

-- 0. Solo sobre una base ya migrada: si no, alembic_version la crearían después las
--    migraciones y heredaría los permisos del paso 4 (/code-review)
DO $$
BEGIN
    IF to_regclass('public.alembic_version') IS NULL THEN
        RAISE EXCEPTION 'Primero alembic upgrade head: falta alembic_version';
    END IF;
END
$$;

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
REVOKE ALL ON public.alembic_version FROM rydercup_app;

-- 6. n8n ya no lee sola cada tabla nueva (auditoría de la fase 6, DB-03; decidido por
--    Agustín el 14 nov 2026). Sus permisos de hoy (las 4 tablas del informe de los lunes,
--    dados a mano) no cambian; si necesita otra, se le da a mano. backup_ro sí sigue
--    leyendo las tablas nuevas: las copias tienen que llevarlas
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n_lectura') THEN
        ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM n8n_lectura;
    END IF;
END
$$;
